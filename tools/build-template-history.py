#!/usr/bin/env python3
"""Rebuild skills/project-update/history/ from git: every version of every project
template this plugin has ever shipped, content-addressed by sha256.

  tools/build-template-history.py             write index.json and the blobs
  tools/build-template-history.py --dry-run   list the blobs a real run would delete

The shared tree ai/ is recorded under the ai-init/.ai/ keys its files shipped
under before they moved there. Those keys keep their hashes and lose their
blobs: a project copy of a shared file is only ever classified, never merged,
so a blob is written only when a key outside the shared set references it.

/project-update uses it to tell a file the user never touched (its content is a
version we shipped) from one they edited, and to find the base for a three-way
merge. Run it after changing anything under skills/*/templates and commit the
result; tests/test-project-update.sh fails while it is stale.
"""
import hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (key prefix, directory). The shared tree ai/ keeps the keys its files had
# while ai-init shipped them as .ai/<path>, so a project copy still matches.
SETS = [("ai-init", "skills/ai-init/templates"), ("project-init", "skills/project-init/templates"),
        ("ai-init/.ai", "ai")]
OUT = os.path.join(ROOT, "skills", "project-update", "history")


def git(*args, raw=False):
    out = subprocess.run(["git", "-C", ROOT, *args], check=True, capture_output=True).stdout
    return out if raw else out.decode()


def shared_keys(index):
    """ai-init/.ai/<rel> with ai/<rel> present: read from the plugin, never merged."""
    prefix = "ai-init/.ai/"
    return {k for k in index if k.startswith(prefix) and os.path.isfile(os.path.join(ROOT, "ai", k[len(prefix):]))}


def main(argv):
    dry_run = argv == ["--dry-run"]
    if argv and not dry_run:
        sys.exit(__doc__)
    index, blobs = {}, {}

    def add(key, content):
        sha = hashlib.sha256(content).hexdigest()
        blobs[sha] = content
        versions = index.setdefault(key, [])
        if sha not in versions:
            versions.append(sha)

    # Every ref, not only HEAD: a template shipped from a feature branch or an
    # install made before a merge is still a version a project may carry.
    commits = git("rev-list", "--reverse", "--all", "--", *(root for _, root in SETS)).split()
    for commit in commits:
        for name, root in SETS:
            for path in git("ls-tree", "-r", "--name-only", commit, "--", root).splitlines():
                add("%s/%s" % (name, os.path.relpath(path, root)), git("show", "%s:%s" % (commit, path), raw=True))
    # The working tree too, so uncommitted template edits are covered before the commit.
    for name, root in SETS:
        base = os.path.join(ROOT, root)
        for dirpath, _, files in os.walk(base):
            for f in files:
                full = os.path.join(dirpath, f)
                with open(full, "rb") as fh:
                    add("%s/%s" % (name, os.path.relpath(full, base)), fh.read())

    shared = shared_keys(index)
    keep = {sha for key, versions in index.items() if key not in shared for sha in versions}
    blobs = {sha: content for sha, content in blobs.items() if sha in keep}
    os.makedirs(os.path.join(OUT, "blobs"), exist_ok=True)
    stale = sorted(set(os.listdir(os.path.join(OUT, "blobs"))) - set(blobs))
    if dry_run:
        for name in stale:
            print(name)
        print("dry run: %d blobs would be deleted, %d kept, %d shared keys" % (len(stale), len(blobs), len(shared)),
              file=sys.stderr)
        return 0
    for sha, content in blobs.items():
        path = os.path.join(OUT, "blobs", sha)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(content)
    for name in stale:
        os.remove(os.path.join(OUT, "blobs", name))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(index.items())), fh, indent=1)
        fh.write("\n")
    print("history: %d files, %d blobs, %d commits; %d shared keys hash only"
          % (len(index), len(blobs), len(commits), len(shared)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
