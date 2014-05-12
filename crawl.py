import json
import logging
import logging.config
import posixpath
import re
import urlparse

import cachecontrol
import html5lib
import requests


logger = logging.getLogger("crawl")


class Session(requests.Session):

    timeout = None

    def request(self, method, url, *args, **kwargs):
        # Allow setting a default timeout on a session
        kwargs.setdefault("timeout", self.timeout)

        # Dispatch the actual request
        return super(Session, self).request(method, url, *args, **kwargs)


def is_installable(url):
    # We want to just check based on the path
    path = urlparse.urlparse(url).path

    # Check if our file ends with any of our installable package extensions
    for ext in {".tar", ".tar.gz", "tar.bz2", ".zip", ".tgz", ".egg", ".whl"}:
        if path.endswith(ext):
            break
    else:
        # If we've gotten to this point, then this URL isn't an installable
        # file
        return False

    return True


def is_safe(url):
    return bool(
        re.search(
            r"(sha1|sha224|sha384|sha256|sha512|md5)=([a-f0-9]+)",
            url,
        )
    )


def list_all_projects(session):
    resp = session.get("https://pypi.python.org/simple/")
    html = html5lib.parse(resp.content, namespaceHTMLElements=False)
    return [e.text for e in html.findall(".//a")]


def process_project(session, project):
    url = "https://pypi.python.org/simple/{}/".format(project)

    try:
        resp = session.get(url)
        resp.raise_for_status()
    except Exception:
        logger.exception("An error occurred fetching %s", url)
        return [], [], []

    html = html5lib.parse(resp.content, namespaceHTMLElements=False)

    internal = set()
    external = set()
    unsafe = set()
    additional_urls = set()

    for anchor in html.findall(".//a"):
        url = anchor.get("href")
        if not url:
            continue

        try:
            filename = posixpath.basename(urlparse.urlparse(url).path)
        except Exception:
            logger.exception("An error occurred parsing %s", url)
            continue

        # Pull out our internal links
        if anchor.get("rel") and "internal" in anchor.get("rel").split():
            internal.add(filename)

        # Pull out any direct links which count as "external"
        if is_installable(url) and is_safe(url):
            external.add(filename)

        # Pull out any direct links which count as "unsafe"
        if is_installable(url) and not is_safe(url):
            unsafe.add(filename)

        # Pull out any urls which need to be scraped
        if (anchor.get("rel")
                and set(anchor.get("rel").split()) & {"download", "homepage"}
                and not is_installable(url)):
            additional_urls.add(url)

    for url in additional_urls:
        try:
            resp = session.get(url)
            resp.raise_for_status()

            html = html5lib.parse(resp.content, namespaceHTMLElements=False)

            for anchor in html.findall(".//a"):
                url = anchor.get("href")
                if not url:
                    continue

                filename = posixpath.basename(urlparse.urlparse(url).path)

                # Pull out any link which looks installable, since these come
                # from scraped pages they always count as unsafe.
                if is_installable(url):
                    unsafe.add(filename)
        except Exception:
            logger.exception("An error occurred fetching %s", url)
            continue

    # Files can exist in multiple places, we only want to count each particular
    # file once. In order to decide where to classify any particular file we'll
    # use a priority system. We prefer internal, than external, and finally
    # unsafe.

    unsafe = unsafe - (internal | external)

    external = external - internal

    return sorted(internal), sorted(external), sorted(unsafe)


def process_all():
    session = Session()
    session.timeout = 5
    session = cachecontrol.CacheControl(session)

    return {
        p: process_project(session, p)
        for p in list_all_projects(session)
    }


def main():
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "DEBUG",
        }
    })

    with open("data.json", "w") as fp:
        json.dump(process_all(), fp, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
