#!/usr/bin/env python3
"""Print the section of CHANGELOG.md for a given version, for the GitHub Release notes.

  tools/changelog-section.py 4.1.0                 the body under "## [4.1.0] ..."
  tools/changelog-section.py 4.1.0 --file PATH     read PATH (default: CHANGELOG.md in the repository root)

The heading line is left out; the body runs to the next line starting "## [" (or the end
of the file), with leading and trailing blank lines trimmed. "## [Unreleased]" is never
returned for a version. A version is X.Y.Z, optionally -prerelease.
Exit 0 ok, 1 no section for the version or an empty one, 2 a refused version or a usage error.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?")


def section(lines, version):
    """The body lines of the section headed "## [version]", or None when there is none."""
    head = "## [" + version + "]"
    body = None
    for line in lines:
        if body is None:
            if line.startswith(head):
                body = []
        elif line.startswith("## ["):
            break
        else:
            body.append(line)
    if body is None:
        return None
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return body


def main(argv):
    """Entry point; returns the exit code."""
    parser = argparse.ArgumentParser(description="Print the CHANGELOG section for a given version.")
    parser.add_argument("version", help="X.Y.Z or X.Y.Z-prerelease")
    parser.add_argument("--file", default=os.path.join(ROOT, "CHANGELOG.md"), help="the changelog to read")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    if not VERSION.fullmatch(args.version):
        print("refused version: " + args.version, file=sys.stderr)
        return 2
    try:
        with open(args.file, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as err:
        print("cannot read %s: %s" % (args.file, err), file=sys.stderr)
        return 2
    body = section(lines, args.version)
    if body is None:
        print("%s has no section for %s" % (args.file, args.version), file=sys.stderr)
        return 1
    if not body:
        print("%s has an empty section for %s" % (args.file, args.version), file=sys.stderr)
        return 1
    print("\n".join(body))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
