#!/usr/bin/env python3
"""Rebuild skills/project-update/history/ from git: every version of every project
template this plugin has ever shipped, content-addressed by sha256.

  tools/build-template-history.py

/project-update uses it to tell a file the user never touched (its content is a
version we shipped) from one they edited, and to find the base for a three-way
merge. Run it after changing anything under skills/*/templates and commit the
result; tests/test-project-update.sh fails while it is stale.
"""
import hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS = {"ai-init": "skills/ai-init/templates", "project-init": "skills/project-init/templates"}
OUT = os.path.join(ROOT, "skills", "project-update", "history")


def git(*args, raw=False):
    out = subprocess.run(["git", "-C", ROOT, *args], check=True, capture_output=True).stdout
    return out if raw else out.decode()


def main():
    index, blobs = {}, {}

    def add(key, content):
        sha = hashlib.sha256(content).hexdigest()
        blobs[sha] = content
        versions = index.setdefault(key, [])
        if sha not in versions:
            versions.append(sha)

    # Every ref, not only HEAD: a template shipped from a feature branch or an
    # install made before a merge is still a version a project may carry.
    commits = git("rev-list", "--reverse", "--all", "--", *SETS.values()).split()
    for commit in commits:
        for name, root in SETS.items():
            for path in git("ls-tree", "-r", "--name-only", commit, "--", root).splitlines():
                add("%s/%s" % (name, os.path.relpath(path, root)), git("show", "%s:%s" % (commit, path), raw=True))
    # The working tree too, so uncommitted template edits are covered before the commit.
    for name, root in SETS.items():
        base = os.path.join(ROOT, root)
        for dirpath, _, files in os.walk(base):
            for f in files:
                full = os.path.join(dirpath, f)
                add("%s/%s" % (name, os.path.relpath(full, base)), open(full, "rb").read())

    os.makedirs(os.path.join(OUT, "blobs"), exist_ok=True)
    for sha, content in blobs.items():
        path = os.path.join(OUT, "blobs", sha)
        if not os.path.exists(path):
            open(path, "wb").write(content)
    for stale in set(os.listdir(os.path.join(OUT, "blobs"))) - set(blobs):
        os.remove(os.path.join(OUT, "blobs", stale))
    with open(os.path.join(OUT, "index.json"), "w") as fh:
        json.dump(dict(sorted(index.items())), fh, indent=1)
        fh.write("\n")
    print("history: %d files, %d versions, %d commits" % (len(index), len(blobs), len(commits)))


if __name__ == "__main__":
    sys.exit(main())
