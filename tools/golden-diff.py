#!/usr/bin/env python3
"""List the guard-characterization records that changed, by record.

  tools/golden-diff.py                  the working golden against HEAD's
  tools/golden-diff.py --base REV       against REV's
  tools/golden-diff.py OLD NEW          two golden files
  tools/golden-diff.py --record         re-record the golden from the port, then diff

A record is a "### <guard> | <label>" header and the lines up to the next one.
A header can repeat, so a record is keyed by its header and its occurrence.
Prints one line per record — "changed", "added" or "removed", then the key —
and a count; exits 1 when anything moved, 0 when the two are byte-identical.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = "tests/fixtures/guard-characterization/golden.txt"


def records(data):
    out, seen, key = {}, {}, None
    # The file's final newline would otherwise belong to the last record only.
    for line in data[:-1].split(b"\n") if data.endswith(b"\n") else data.split(b"\n"):
        if line.startswith(b"### "):
            head = line[4:].decode("utf-8", "replace")
            seen[head] = seen.get(head, 0) + 1
            key = head if seen[head] == 1 else "%s #%d" % (head, seen[head])
            out[key] = []
        elif key is not None:
            out[key].append(line)
    return out


def record():
    """The corpus through the port, written over the golden."""
    sys.path.insert(0, ROOT)
    from tests.test_guard_characterization import Tree, port_argv, run_corpus  # pylint: disable=import-outside-toplevel,import-error  # ROOT is put on sys.path just above
    tree = Tree()
    try:
        got = b"".join(rec for _, _, rec in run_corpus(tree, port_argv))
    finally:
        tree.close()
    with open(os.path.join(ROOT, GOLDEN), "wb") as fh:
        fh.write(got)


def main(argv):
    if argv[:1] == ["--record"]:
        record()
        argv = argv[1:]
    base = "HEAD"
    if argv[:1] == ["--base"]:
        base, argv = argv[1], argv[2:]
    if len(argv) == 2:
        with open(argv[0], "rb") as fh:
            old = fh.read()
        new_path = argv[1]
    elif not argv:
        old = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (base, GOLDEN)],
                             check=True, capture_output=True).stdout
        new_path = os.path.join(ROOT, GOLDEN)
    else:
        sys.exit(__doc__)
    with open(new_path, "rb") as fh:
        new = fh.read()
    a, b = records(old), records(new)
    moved = [("changed", k) for k in a if k in b and a[k] != b[k]]
    moved += [("added", k) for k in b if k not in a] + [("removed", k) for k in a if k not in b]
    for what, key in moved:
        print("%-8s %s" % (what, key))
    print("%d of %d records moved" % (len(moved), len(set(a) | set(b))))
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
