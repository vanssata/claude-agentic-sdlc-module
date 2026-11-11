"""The packages on disk: loading them, the id and seal lookups over them, the batch ledger and the open
batch an export writes into."""
import collections
import contextlib
import json
import os
import random

import memory_format as mf
import memory_io as mio


# ------------------------------------------------------------------ packages on disk
def load_packages(root):
    """{name: (header, entries, errors)} for every package in the working tree."""
    out = {}
    base = mio.memory_dir(root)
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".jsonl"):
            out[name] = mf.parse_package(mio.read_bytes(os.path.join(base, name)) or b"", name)
    return out


def all_rids(packages):
    return {e["rid"] for _, entries, _ in packages.values() for e in entries}


def seals_by_key(packages):
    out = collections.defaultdict(list)
    for name, (_, entries, _) in packages.items():
        for e in entries:
            if e.get("kind") == "task":
                out[mf.key_of(e)].append((name, e))
    return out


def read_batches(root):
    with contextlib.suppress(OSError, ValueError):
        data = mio.read_json(mio.local_path(root, "batches.json"))
        if isinstance(data, dict) and isinstance(data.get("open"), dict):
            return data
    return {"schema": 1, "open": {}}


def write_batches(root, data):
    mio.atomic_write(mio.local_path(root, "batches.json"), json.dumps(data, sort_keys=True, indent=1) + "\n")


def new_batch_name(root, period, author):
    rng = random.SystemRandom()
    for _ in range(64):
        batch = "".join(rng.choice(mio.BATCH_CHARS) for _ in range(4))
        name = mf.package_name(period, author, batch)
        if not os.path.exists(os.path.join(mio.memory_dir(root), name)):
            return name
    raise mio.MemoryError_("no free batch name for %s.%s" % (period, author), 3)


def open_batch(root, cfg, stamp=None):
    """The branch's open batch, reused while it is in the tree, the author's,
    of the current period and under package_max_bytes; else a new name.
    Called under the lock."""
    stamp = stamp or mio.now()
    period = mf.period_of(stamp, cfg.period)
    branch = mio.current_branch(root)
    books = read_batches(root)
    name = books["open"].get(branch)
    if name:
        parts = mf.parse_package_name(name)
        path = os.path.join(mio.memory_dir(root), name)
        header = None
        data = mio.read_bytes(path)
        if data:
            header, _, _ = mf.parse_package(data.split(b"\n", 1)[0] + b"\n", name)
        if parts and data and header and header.get("author") == cfg.author and parts["period"] == period \
                and parts["batch"] and len(data) < cfg.package_max_bytes:
            return name, branch, books
    name = new_batch_name(root, period, cfg.author)
    return name, branch, books


def sealed_task_ids(packages):
    return {e.get("task") for _, entries, _ in packages.values() for e in entries if e.get("kind") == "task"}
