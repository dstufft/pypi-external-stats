from __future__ import division

import fileinput
import json


def process(data):
    processed = {
        "internal": [],
        "external1": [],
        "external2": [],
        "unsafe": [],
    }
    for project, (internal, external, unsafe) in data.iteritems():
        total = len(internal + external + unsafe)

        if internal:
            processed["internal"].append(project)

        if external:
            # Figure out what percent of them are external
            percent = (len(external) / total) * 100

            if percent < 50:
                processed["external1"].append(project)
            else:
                processed["external2"].append(project)

        if unsafe:
            processed["unsafe"].append(project)

    return {k: sorted(v) for k, v in processed.iteritems()}


def main():
    # Load data
    data = json.loads("".join([line for line in fileinput.input()]))

    # Process Data
    processed = process(data)

    # Print some data
    print("Hosted on PyPI: {}".format(len(processed["internal"])))
    print("Hosted Externally (<50%): {}".format(len(processed["external1"])))
    print("Hosted Externally (>50%): {}".format(len(processed["external2"])))
    print("Hosted Externally: {}".format(
        len(processed["external1"] + processed["external2"])
    ))
    print("Hosted Unsafely: {}".format(len(processed["unsafe"])))

    # Save data
    with open("processed.json", "w") as fp:
        json.dump(processed, fp, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
