#!/usr/bin/env python3
"""Run every tests/test_*.py in its own `python3 -I` process, concurrently.

    python3 -I tests/run_suite.py [FILE...] [--start DIR=tests] [--pattern GLOB=test_*.py]
                                  [--jobs N=cpu_count] [--timeout S=600] [--serial ID]...
                                  [--collect]

Each file is loaded exactly as `unittest discover -s DIR -p FILE` loads it, so the test ids
are the same; `--collect` prints them. The ids named by `--serial` (default
test_guard_characterization.TestTimed, whose budgets are wall-clock) are left out of the
parallel phase and run alone afterwards. The output ends with the unittest tail
(`Ran N tests in Xs`, then OK / OK (skipped=N) / FAILED (...)).

Fail-safe: exit 1 for a failure, an error, an import error, an unexpected success, a crash
or a missing or unreadable result, a timeout, an interruption. No fail-fast. Exit 2 is
usage. Nothing is written in the repository: the results and logs live in a temporary
directory that is removed at exit. The environment reaches the children unchanged.
"""
import argparse
import concurrent.futures
import fnmatch
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

DEFAULT_SERIAL = "test_guard_characterization.TestTimed"
RESULT_KEYS = ("file", "tests", "failures", "errors", "skipped", "unexpected_successes",
               "expected_failures", "seconds", "exit")
SELF = os.path.abspath(__file__)


# ---------------------------------------------------------------------------------------
# ids and results


def id_matches(test_id, wanted):
    return test_id == wanted or test_id.startswith(wanted + ".")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def collect(start, pattern):
    """The sorted ids `unittest discover -s START -p PATTERN` would run."""
    suite = unittest.TestLoader().discover(start, pattern=pattern, top_level_dir=start)
    return sorted(t.id() for t in flatten(suite))


def read_result(path):
    """The child's result as a dict, or None when it is missing, unreadable or malformed."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or any(k not in data for k in RESULT_KEYS):
        return None
    if not isinstance(data["file"], str):
        return None
    for key in RESULT_KEYS[1:]:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
    return data


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


# ---------------------------------------------------------------------------------------
# the child: one file, or one serial id of it


def run_child(args):
    suite = unittest.TestLoader().discover(args.start, pattern=os.path.basename(args.child),
                                           top_level_dir=args.start)
    tests = list(flatten(suite))
    if args.only:
        tests = [t for t in tests if any(id_matches(t.id(), w) for w in args.only)]
    tests = [t for t in tests if not any(id_matches(t.id(), w) for w in args.exclude)]
    t0 = time.monotonic()
    result = unittest.TextTestRunner(failfast=False).run(unittest.TestSuite(tests))
    data = {
        "file": os.path.basename(args.child),
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "expected_failures": len(result.expectedFailures),
        "seconds": round(time.monotonic() - t0, 3),
        "exit": 0 if result.wasSuccessful() else 1,
    }
    tmp = args.result + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, args.result)
    return data["exit"]


# ---------------------------------------------------------------------------------------
# the parent: children in their own process groups


class Children:
    """The live process groups, so a signal can end every one of them."""

    def __init__(self):
        self.lock = threading.RLock()
        self.groups = set()
        self.stopping = False

    def add(self, pgid):
        with self.lock:
            self.groups.add(pgid)
            if self.stopping:
                kill_group(pgid)

    def discard(self, pgid):
        with self.lock:
            self.groups.discard(pgid)

    def kill_all(self):
        with self.lock:
            self.stopping = True
            for pgid in list(self.groups):
                kill_group(pgid)


def kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def read_log(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def child_job(children, tmp, key, start, name, timeout, exclude=(), only=()):
    """Run one child to its end and judge it. Returns the verdict dict (never raises)."""
    out = {"name": name, "file": os.path.basename(name), "status": "FAIL", "tests": 0, "failures": 0,
           "errors": 0, "skipped": 0, "unexpected": 0, "expected": 0, "seconds": 0.0,
           "detail": "", "why": "", "log": ""}
    result_path = os.path.join(tmp, key + ".json")
    log_path = os.path.join(tmp, key + ".log")
    cmd = [sys.executable, "-I", SELF, "--child", out["file"], "--result", result_path, "--start", start]
    for item in exclude:
        cmd += ["--exclude", item]
    for item in only:
        cmd += ["--only", item]
    t0 = time.monotonic()
    timed_out = False
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        children.add(proc.pid)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_group(proc.pid)
            proc.wait()
        finally:
            children.discard(proc.pid)
    elapsed = time.monotonic() - t0
    rc = proc.returncode
    out["log"] = read_log(log_path)
    if timed_out:
        out.update(status="TIME", seconds=elapsed, why="timed out after %ds" % timeout,
                   detail="timed out after %ds" % timeout)
        return out
    data = read_result(result_path)
    if data is None:
        lost = "unreadable result" if os.path.exists(result_path) else "no result file"
        out.update(seconds=elapsed, why="%s, exit %s" % (lost, rc), detail="%s (exit %s)" % (lost, rc))
        return out
    out.update(tests=int(data["tests"]), failures=int(data["failures"]), errors=int(data["errors"]),
               skipped=int(data["skipped"]), unexpected=int(data["unexpected_successes"]),
               expected=int(data["expected_failures"]), seconds=float(data["seconds"]))
    if data["file"] != out["file"]:
        out.update(why="result of %s, exit %s" % (data["file"], rc),
                   detail="result belongs to %s (exit %s)" % (data["file"], rc))
    elif rc != 0 or data["exit"] != 0 or out["failures"] or out["errors"] or out["unexpected"]:
        out.update(why="exit %s" % (rc if rc != 0 else data["exit"] or 1),
                   detail="failures=%d errors=%d" % (out["failures"], out["errors"])
                   + (" unexpected=%d" % out["unexpected"] if out["unexpected"] else ""))
    else:
        out["status"] = "ok"
    return out


def format_line(res, serial=False):
    if serial:
        head = "serial %s  %s" % (res["status"], res["name"])
    else:
        head = "%-4s  %-28s" % (res["status"], res["name"])
    if res["status"] == "TIME" or (res["status"] == "FAIL" and not res["tests"] and res["detail"]):
        return "%s  %s" % (head, res["detail"])
    line = "%s  %s  %.1fs" % (head, plural(res["tests"], "test"), res["seconds"])
    if res["status"] != "ok":
        line += "  " + res["detail"]
    return line


def red_section(name, res):
    return ["==== FAIL %s (%s) ====" % (name, res["why"]), res["log"].rstrip("\n"), "==== end %s ====" % name]


def summarize(results, serial_results, elapsed=0.0):
    """The red sections, then the unittest tail. Returns (text, exit_code)."""
    every = list(results) + list(serial_results)
    out = []
    for prefix, group in (("", results), ("serial ", serial_results)):
        for res in group:
            if res["status"] != "ok":
                out += red_section(prefix + res["name"], res)
    ran = sum(r["tests"] for r in every)
    failures = sum(r["failures"] for r in every)
    errors = sum(r["errors"] for r in every)
    lost = sum(1 for r in every if r["status"] != "ok" and not r["tests"] and not (r["failures"] or r["errors"]))
    errors += lost
    bits = []
    red = [r for r in every if r["status"] != "ok"]
    if red:
        if failures:
            bits.append("failures=%d" % failures)
        if errors:
            bits.append("errors=%d" % errors)
    for label, key in (("skipped", "skipped"), ("expected failures", "expected"),
                       ("unexpected successes", "unexpected")):
        n = sum(r[key] for r in every)
        if n:
            bits.append("%s=%d" % (label, n))
    out.append("-" * 70)
    out.append("Ran %s in %.3fs" % (plural(ran, "test"), elapsed))
    out.append("")
    verdict = "FAILED" if red else "OK"
    out.append(verdict + (" (%s)" % ", ".join(bits) if bits else ""))
    return "\n".join(out), (1 if red else 0)


# ---------------------------------------------------------------------------------------
# the command line


def usage(parser, message):
    parser.error(message)  # prints the usage and exits 2


def build_parser():
    p = argparse.ArgumentParser(prog="run_suite.py", description=__doc__.split("\n\n")[0])
    p.add_argument("files", nargs="*", metavar="FILE", help="test files in --start (default: all that match --pattern)")
    p.add_argument("--start", default="tests", help="directory of the test files (default: tests)")
    p.add_argument("--pattern", default="test_*.py", help="glob for test files (default: test_*.py)")
    p.add_argument("--jobs", type=int, default=None, help="concurrent files (default: cpu count)")
    p.add_argument("--timeout", type=int, default=600, help="seconds per file (default: 600)")
    p.add_argument("--serial", action="append", metavar="ID",
                   help="a test id run alone after the parallel phase (default: %s)" % DEFAULT_SERIAL)
    p.add_argument("--collect", action="store_true", help="print the test ids and exit")
    # internal
    p.add_argument("--child", metavar="FILE", help=argparse.SUPPRESS)
    p.add_argument("--result", help=argparse.SUPPRESS)
    p.add_argument("--exclude", action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("--only", action="append", default=[], help=argparse.SUPPRESS)
    return p


def select_files(parser, args, start):
    if not args.files:
        names = sorted(n for n in os.listdir(start)
                       if fnmatch.fnmatchcase(n, args.pattern) and os.path.isfile(os.path.join(start, n)))
        if not names:
            usage(parser, "no test files matching %s in %s" % (args.pattern, start))
        return names
    names = []
    for item in args.files:
        folder = os.path.realpath(os.path.dirname(os.path.abspath(item))) if os.path.dirname(item) else \
            os.path.realpath(start)
        name = os.path.basename(item)
        if folder != os.path.realpath(start):
            usage(parser, "%s is not in --start %s" % (item, start))
        if not fnmatch.fnmatchcase(name, args.pattern) or not os.path.isfile(os.path.join(start, name)):
            usage(parser, "%s is not a test file matching %s in %s" % (item, args.pattern, start))
        if name not in names:
            names.append(name)
    return names


def check_serial(parser, args, start, names):
    """The serial ids that apply. An explicit id that matches nothing is a usage error."""
    explicit = bool(args.serial)
    kept = []
    for wanted in args.serial or [DEFAULT_SERIAL]:
        fname = wanted.split(".")[0] + ".py"
        if fname not in names:
            if explicit:
                usage(parser, "--serial %s: %s is not among the files" % (wanted, fname))
            continue
        ids = collect(start, fname)
        broken = any(i.startswith("unittest.loader.") for i in ids)
        if not broken and not any(id_matches(i, wanted) for i in ids):
            usage(parser, "--serial %s matches no test in %s" % (wanted, fname))
        kept.append(wanted)
    return kept


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.child:
        return run_child(args)
    if args.jobs is not None and args.jobs < 1:
        usage(parser, "--jobs must be at least 1")
    if args.timeout < 1:
        usage(parser, "--timeout must be at least 1")
    start = os.path.abspath(args.start)
    if not os.path.isdir(start):
        usage(parser, "--start %s is not a directory" % args.start)
    names = select_files(parser, args, start)
    if args.collect:
        ids = []
        for name in names:
            ids += collect(start, name)
        print("\n".join(sorted(ids)))
        return 0
    serial = check_serial(parser, args, start, names)
    jobs = min(args.jobs or os.cpu_count() or 1, len(names))
    return run_all(start, names, serial, jobs, args.timeout)


def run_all(start, names, serial, jobs, timeout):
    t0 = time.monotonic()
    children = Children()
    tmp = tempfile.mkdtemp(prefix="run_suite-")

    def interrupted(signum, _frame):
        children.kill_all()
        shutil.rmtree(tmp, ignore_errors=True)
        sys.stdout.flush()
        sys.stderr.write("run_suite: interrupted by signal %d, children killed\n" % signum)
        sys.stderr.flush()
        os._exit(1)

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    try:
        print("run_suite: %s, %s%s" % (plural(len(names), "file"), plural(jobs, "job"),
                                       ", serial after: " + ", ".join(serial) if serial else ""), flush=True)
        order = sorted(names, key=lambda n: (-os.path.getsize(os.path.join(start, n)), n))
        results, serial_results = [], []
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            pending = {pool.submit(child_job, children, tmp, "f%d" % i, start, name, timeout,
                                   [s for s in serial if s.split(".")[0] + ".py" == name]): name
                       for i, name in enumerate(order)}
            while pending:
                done, _ = concurrent.futures.wait(pending, timeout=0.5,
                                                  return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    pending.pop(fut)
                    res = fut.result()
                    results.append(res)
                    print(format_line(res), flush=True)
        for i, wanted in enumerate(serial):
            res = child_job(children, tmp, "s%d" % i, start, wanted.split(".")[0] + ".py", timeout,
                            only=[wanted])
            res["name"] = wanted
            serial_results.append(res)
            print(format_line(res, serial=True), flush=True)
        text, code = summarize(results, serial_results, time.monotonic() - t0)
        print(text, flush=True)
        return code
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
