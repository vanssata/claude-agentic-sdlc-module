#!/usr/bin/env python3
"""Check or set the one version the riskrails package carries in five places.

  tools/sync-version.py --check                  exit 0 when all five agree
  tools/sync-version.py --check --tag v3.0.1     also: the tag must equal package.json's version
  tools/sync-version.py 3.0.2                    rewrite the version in all five places
  tools/sync-version.py ... --root DIR           act on the tree at DIR (default: this repository)

The places: package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json
(two "version" keys), .codex-plugin/plugin.json. Setting replaces only the value of
each "version" key, so every other byte survives. A version is X.Y.Z, optionally
-prerelease. Exit 0 ok, 1 a mismatch, 2 a refused version or a usage error.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("package.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
         ".codex-plugin/plugin.json")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
KEY = re.compile(r'("version"\s*:\s*")([^"]*)(")')


def read(root, name):
    """The text of one file, bytes kept (no newline translation)."""
    with open(os.path.join(root, name), encoding="utf-8", newline="") as fh:
        return fh.read()


def versions(root):
    """[(file, version)] for every "version" key in the five places."""
    found = []
    for name in FILES:
        for match in KEY.finditer(read(root, name)):
            found.append((name, match.group(2)))
    return found


def check(root, tag):
    """Exit status of --check; prints each file:version on a mismatch."""
    found = versions(root)
    pkg = [v for n, v in found if n == "package.json"]
    expected = pkg[0] if pkg else None
    bad = len(found) != 5 or any(v != expected for _, v in found)
    if tag is not None and tag.removeprefix("v") != expected:
        bad = True
        print("tag %s != package.json %s" % (tag, expected))
    if bad:
        for name, version in found:
            print("%s:%s" % (name, version))
    return 1 if bad else 0


def setv(root, version):
    """Rewrite every "version" value; returns 0."""
    for name in FILES:
        text = KEY.sub(lambda m: m.group(1) + version + m.group(3), read(root, name))
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return 0


def main(argv):
    """Entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version", nargs="?")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    if args.check == bool(args.version) or (args.tag and not args.check):
        ap.error("give either --check [--tag T] or a version")
    if args.check:
        return check(args.root, args.tag)
    if not VERSION.fullmatch(args.version):
        print("refused: %r is not X.Y.Z[-prerelease]" % args.version, file=sys.stderr)
        return 2
    return setv(args.root, args.version)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
