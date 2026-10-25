"""weight.py and `state.py weight`: the SQ1 validation table, the declaration and
hint rules, the grep budget, the mirror, and the seven-line output.

Every tree here is synthetic (FC-S4): a few files shaped like the journaled task
each SQ1 row was scored from, never a copy of one.
"""
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import weight  # noqa: E402  pylint: disable=wrong-import-position

STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
SHIPPED_DIR = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies")


def refs(ident, n, where="src/ref"):
    """n plain files that mention `ident`, so its reference count is n."""
    return {"%s%d.txt" % (where, i): "uses %s here\n" % ident for i in range(n)}


class Tree:
    """A scratch project: files from a dict, optionally a git repository."""

    def __init__(self, files, git=True):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".ai"))
        for rel, text in files.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        if git:
            subprocess.run(["git", "init", "-q", self.root], check=True)

    def score(self, files, declared=None, goal="", policy=None):
        return weight.compute(self.root, files, declared or {}, goal, policy=policy)

    def close(self):
        self.tmp.cleanup()


def zero(*axes):
    return {a: (0, "none (synthetic)") for a in axes}


def one(*axes):
    return {a: (1, "limited (synthetic)") for a in axes}


class TestSQ1(unittest.TestCase):
    """The spec's SQ1 table: each row's axes, W and mode."""

    def check(self, tree_files, files, declared, axes, mode, policy=None):
        tree = Tree(tree_files)
        try:
            result = tree.score(files, declared, policy=policy)
        finally:
            tree.close()
        got = tuple(result.axes[a] for a in weight.AXES)
        self.assertEqual(got, axes, weight.render(result, long=True))
        self.assertEqual(result.w, sum(axes))
        self.assertEqual(result.mode, mode, weight.render(result, long=True))
        return result

    def test_font_in_login_template(self):
        # new-shop 09-23-009: a Sylius theme template; the auth-shaped name is a hint.
        f = "themes/shop/templates/login.html.twig"
        r = self.check({f: "<link font>\n"}, [f], zero("behaviour", "novelty"), (0, 0, 0, 1, 0, 0), "light")
        self.assertTrue(r.hints and r.hints[0].startswith("domain +1"))

    def test_odoo_vat_module(self):
        rules, report = "addons/vat/account/vat_rules.py", "addons/vat/account/vat_report.py"
        files = {rules: "x = 1\n", report: "y = 2\n", "tests/test_vat_rules.py": "pass\n"}
        files.update(refs("vat_rules", 6))
        self.check(files, [rules, report], one("behaviour", "novelty"), (2, 1, 0, 2, 1, 1), "full")

    def test_enum_fixture_in_migrations_data(self):
        load = "src/Acme/EnumBundle/Migrations/Data/ORM/LoadEnumData.php"
        enum = "src/Acme/EnumBundle/Entity/EnumValue.php"
        files = {load: "<?php\n", enum: "<?php\n", "tests/Unit/EnumValueTest.php": "<?php\n"}
        files.update(refs("LoadEnumData", 2, "src/a"))
        files.update(refs("EnumValue", 2, "src/b"))
        declared = dict(one("behaviour", "domain"), **zero("novelty"))
        self.check(files, [load, enum], declared, (1, 1, 1, 1, 0, 1), "guarded")

    def test_generated_ddl_in_a_test_fixture(self):
        f = "tests/fixtures/ddl/schema.sql"
        ddl = "".join("CREATE TABLE t%d (id int);\nDROP TABLE t%d;\n" % (i, i) for i in range(900))
        self.check({f: ddl}, [f], {}, (0, 0, 0, 0, 0, 0), "light")

    def test_regex_fix_in_a_hot_guard(self):
        f = "hooks/ai-path-guard.sh"
        files = {f: "#!/bin/sh\n", "tests/test-ai-path-guard.sh": "#!/bin/sh\n"}
        declared = dict(one("behaviour"), **zero("domain", "novelty"))
        self.check(files, [f], declared, (2, 1, 0, 0, 0, 0), "guarded")

    def test_migration_deleting_user_files(self):
        mig, upd = "skills/project-update/migrations/0006_retire.py", "skills/project-update/update.py"
        files = {mig: "x = 1\n", upd: "y = 2\n", "tests/test-project-update.sh": "#!/bin/sh\n"}
        files.update(refs("0006_retire", 6))
        declared = {"behaviour": (2, "deletes files"), "domain": (0, "no money"), "novelty": (1, "new walk")}
        r = self.check(files, [mig, upd], declared, (2, 2, 2, 0, 1, 1), "full")
        self.assertIn("touches user trees", r.hints[0])

    def test_argocd_dev_manifest(self):
        f = "k8s/apps/env/dev/values.yaml"
        files = {f: "replicas: 1\n", "argocd/app-dev.txt": "path %s\n" % f}
        declared = dict(one("behaviour"), **zero("domain", "novelty"))
        self.check(files, [f], declared, (1, 1, 1, 0, 0, 0), "guarded")

    def test_argocd_prod_manifest_and_secret(self):
        values, secret = "k8s/apps/env/prod/values.yaml", "k8s/apps/env/prod/secret-db.yaml"
        files = {values: "replicas: 3\n", secret: "kind: Secret\n", "argocd/app-prod.txt": "path %s\n" % values}
        policy = copy.deepcopy(weight.load_policy(ROOT)[0])
        policy["axes"]["domain"]["modules"].append("**/secret*")       # the project's own module list
        declared = dict(one("behaviour"), **zero("novelty"))
        self.check(files, [values, secret], declared, (1, 1, 2, 2, 0, 0), "full_irreversible", policy)

    def test_project_claude_md(self):
        files = {"CLAUDE.md": "# rules\n", "AGENTS.md": "see CLAUDE.md\n"}
        r = self.check(files, ["CLAUDE.md"], zero("domain", "novelty"), (1, 1, 0, 0, 0, 0), "light")
        self.assertIn("pipeline", r.evidence["behaviour"])

    def test_product_editor_feature(self):
        entity, migration = "src/Entity/Product.php", "migrations/Version20261025.php"
        screen, view = "assets/editor/ProductScreen.js", "templates/product/edit.html.twig"
        files = {entity: "<?php\n", migration: "<?php addSql('ALTER TABLE product ADD x');\n",
                 view: "{{ form }}\n", "tests/Entity/ProductTest.php": "<?php\n",
                 "src/Controller/Edit.txt": "render %s\n" % view}
        files.update(refs("Product", 2))
        self.check(files, [entity, migration, screen, view], one("behaviour", "novelty"),
                   (1, 1, 1, 1, 1, 1), "guarded")
        # The worst realistic one — a new mechanism, no tests — is full, which C2 justifies.
        del files["tests/Entity/ProductTest.php"]
        declared = {"behaviour": (2, "new process"), "novelty": (2, "new mechanism")}
        self.check(files, [entity, migration, screen, view], declared, (1, 2, 1, 1, 2, 2), "full")

    def test_learning_workbench_feature(self):
        lessons, grading = "workbench/lessons.py", "workbench/grading.py"
        files = {lessons: "x = 1\n", grading: "y = 2\n", "tests/test_lessons.py": "pass\n"}
        files.update(refs("lessons", 2))
        declared = dict(one("behaviour", "novelty"), **zero("domain"))
        self.check(files, [lessons, grading], declared, (1, 1, 0, 0, 1, 1), "guarded")

    def test_three_lines_in_payment(self):
        f = "src/Payment/Refund.php"
        tree = Tree({f: "<?php\n"})
        try:
            r = tree.score([f])
        finally:
            tree.close()
        self.assertEqual(r.axes["domain"], 2)
        self.assertEqual(r.mode, "full")

    def test_test_only_and_message_text(self):
        self.check({"tests/test_messages.py": "pass\n"}, ["tests/test_messages.py"], {},
                   (0, 0, 0, 0, 0, 0), "light")
        f = "translations/messages.en.yaml"
        self.check({f: "hello: Hello\n"}, [f], zero("behaviour", "domain", "novelty"),
                   (0, 0, 0, 0, 0, 0), "light")


class TestFCD4(unittest.TestCase):
    """FC-D4: three task shapes from each of productEditorApp and Learning
    Workbench, declared the way a session would, all land in guarded."""

    SHAPES = [
        # productEditorApp: a field and its form; a screen; an additive migration.
        (["src/Entity/Product.php", "src/Form/ProductType.php"], one("behaviour"), zero("novelty")),
        (["assets/editor/VariantScreen.js", "templates/product/variants.html.twig", "src/Entity/Product.php"],
         one("behaviour", "novelty"), {}),
        (["migrations/Version20261026.php", "src/Entity/Product.php"], one("behaviour"), zero("novelty")),
        # Learning Workbench: a grader rule; a lesson loader; a CLI flag.
        (["workbench/grading.py", "workbench/rubrics.py", "tests/test_grading.py"], one("behaviour", "novelty"),
         zero("domain")),
        (["workbench/lessons.py", "workbench/loader.py"], one("behaviour", "novelty"), zero("domain")),
        (["workbench/cli.py"], one("behaviour"), zero("novelty", "domain")),
    ]

    def test_all_guarded(self):
        files = {"src/Entity/Product.php": "<?php\n", "src/Form/ProductType.php": "<?php\n",
                 "templates/product/variants.html.twig": "{{ v }}\n", "tests/Entity/ProductTest.php": "<?php\n",
                 "workbench/grading.py": "x\n", "workbench/lessons.py": "x\n", "workbench/loader.py": "x\n",
                 "workbench/cli.py": "x\n", "tests/test_grading.py": "x\n", "tests/test_lessons.py": "x\n"}
        for ident in ("Product", "ProductType", "grading", "lessons", "loader", "cli"):
            files.update(refs(ident, 3, "src/%s_ref" % ident))
        tree = Tree(files)
        try:
            for shape, raised, lowered in self.SHAPES:
                with self.subTest(shape=shape):
                    r = tree.score(shape, dict(raised, **lowered))
                    self.assertEqual(r.mode, "guarded", weight.render(r, long=True))
        finally:
            tree.close()


class TestRules(unittest.TestCase):

    def setUp(self):
        self.tree = None

    def tearDown(self):
        if self.tree:
            self.tree.close()

    def make(self, files, git=True):
        self.tree = Tree(files, git)
        return self.tree

    def test_declaration_below_measurement_is_replaced(self):
        f = "src/Payment/Refund.php"
        r = self.make({f: "<?php\n"}).score([f], {"domain": (0, "only a log line")})
        self.assertEqual(r.axes["domain"], 2)
        self.assertTrue(any("declared 0 below the measurement 2" in n for n in r.notes))

    def test_hint_wins_over_a_lower_declaration(self):
        f = "themes/shop/templates/login.html.twig"
        r = self.make({f: "x\n"}).score([f], {"domain": (0, "a font")})
        self.assertEqual(r.axes["domain"], 1)

    def test_declaration_raises(self):
        f = "hooks/x.sh"
        r = self.make({f: "x\n"}).score([f], {"reversibility": (2, "writes to prod")})
        self.assertEqual((r.axes["reversibility"], r.mode), (2, "full"))
        self.assertIn("(declared)", r.evidence["reversibility"])

    def test_unknown_scores_one_and_is_listed(self):
        f = "lib/thing.py"
        r = self.make({f: "x\n", "tests/test_thing.py": "x\n"}).score([f])
        self.assertEqual((r.axes["behaviour"], r.axes["domain"], r.axes["novelty"]), (1, 1, 1))
        self.assertEqual(r.unknown, ["behaviour", "domain", "novelty"])

    def test_keyword_in_goal_or_file_raises_behaviour(self):
        f = "lib/jobs.py"
        tree = self.make({f: "def run(): pass\n"})
        self.assertEqual(tree.score([f], goal="move the export to a queue").axes["behaviour"], 1)
        with open(os.path.join(tree.root, f), "w", encoding="utf-8") as fh:
            fh.write("with db.transaction():\n    pass\n")
        r = tree.score([f], {"behaviour": (0, "no change")})
        self.assertEqual(r.axes["behaviour"], 1)
        self.assertIn("transaction", r.evidence["behaviour"])

    def test_new_file(self):
        r = self.make({"src/other.php": "<?php new Thing();\n"}).score(["src/New/Thing.php"])
        self.assertEqual((r.axes["scope"], r.axes["behaviour"]), (0, 0))
        self.assertNotIn("scope", r.unknown)

    def test_common_word_basename(self):
        files = {"lib/utils.py": "x\n"}
        files.update(refs("utils", 20))
        files.update({"src/other%d.txt" % i: "nothing\n" for i in range(4)})
        r = self.make(files).score(["lib/utils.py"])
        self.assertEqual(r.axes["scope"], 1)
        self.assertIn("scope", r.unknown)
        self.assertTrue(any("a word, not a reference" in n for n in r.notes))

    def test_grep_budget(self):
        files = {"lib/a.py": "x\n"}
        files.update(refs("a", 7))
        tree = self.make(files)
        saved = weight.GREP_SECONDS
        weight.GREP_SECONDS = 0
        try:
            r = tree.score(["lib/a.py"])
        finally:
            weight.GREP_SECONDS = saved
        self.assertEqual(r.axes["scope"], 1)
        self.assertIn("scope", r.unknown)
        self.assertEqual(tree.score(["lib/a.py"]).axes["scope"], 2)

    def test_more_than_ten_files_is_unknown_past_the_tenth(self):
        files = {"lib/f%02d.py" % i: "x\n" for i in range(12)}
        r = self.make(files).score(sorted(files))
        self.assertEqual(r.axes["scope"], 1)
        self.assertTrue(any("over 10 files" in n for n in r.notes))

    def test_walk_fallback_without_git(self):
        files = {"lib/core.py": "x\n"}
        files.update(refs("core", 3))
        r = self.make(files, git=False).score(["lib/core.py"])
        self.assertEqual(r.axes["scope"], 1)
        self.assertIn("referenced from 3 files", r.evidence["scope"])

    def test_bad_declaration_is_refused(self):
        tree = self.make({"a.py": "x\n"})
        for bad in ({"size": (1, "x")}, {"domain": (3, "x")}):
            with self.assertRaises(ValueError):
                tree.score(["a.py"], bad)

    def test_directory_is_refused(self):
        # Review H1: scored as "new", src/Payment/ came out light, where its file comes out full.
        tree = self.make({"src/Payment/Foo.php": "<?php\n"})
        self.assertEqual(tree.score(["src/Payment/Foo.php"]).mode, "full")
        for declared in ("src/Payment/", "src/Payment", "src/Payment/."):
            with self.assertRaisesRegex(ValueError, "is a directory"):
                tree.score([declared])

    def test_outside_the_root_is_refused(self):
        # Review L1: the keyword scan would read it.
        tree = self.make({"a.py": "x\n"})
        outside = os.path.join(os.path.dirname(tree.root), "secret.py")
        os.symlink(outside, os.path.join(tree.root, "link.py"))
        for declared in (outside, "../secret.py", "src/../../secret.py", "link.py"):
            with self.assertRaisesRegex(ValueError, "is outside"):
                tree.score([declared])

    def test_two_forms_of_one_file_count_once(self):
        # Review L4: the duplicates were removed before the path was normalised.
        tree = self.make({"lib/vat.py": "x\n"})
        r = tree.score(["lib/vat.py", "./lib/vat.py", "lib//vat.py"])
        self.assertEqual(r.evidence["coverage"], "0 of 1 code files have a test")

    def test_glob_semantics(self):
        self.assertTrue(weight.match("src/Payment/X.php", ["**/Payment/**"]))
        self.assertTrue(weight.match("Payment/X.php", ["**/Payment/**"]))
        self.assertTrue(weight.match("sub/composer.json", ["composer.json"]))
        self.assertFalse(weight.match("app/templates/x.twig", ["templates/**"]))
        self.assertFalse(weight.match("src/PaymentX/a.php", ["**/Payment/**"]))


class TestTable(unittest.TestCase):

    def test_shipped_table_shape(self):
        path = os.path.join(SHIPPED_DIR, "weight.json")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertLessEqual(text.count("\n"), 80)
        self.assertNotIn("_comment", text)
        policy = json.loads(text)
        self.assertEqual(set(policy["axes"]), set(weight.AXES))
        self.assertEqual(policy["tests"]["max_suite_runs"], 2)
        self.assertEqual((policy["review_rounds_max"], policy["remediation_rounds"]), (2, 2))

    def test_mirror_fresh(self):
        src, md = os.path.join(SHIPPED_DIR, "weight.json"), os.path.join(SHIPPED_DIR, "weight.md")
        with open(src, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("sha256: %s" % sha, text, "run: state.py --root skills/ai-init/templates weight --mirror")
        self.assertEqual(text, weight.mirror(src))

    def test_line_limits(self):
        with open(weight.__file__, encoding="utf-8") as fh:
            self.assertLessEqual(sum(1 for _ in fh), 300)


class TestCLI(unittest.TestCase):

    def run_state(self, *args, root=ROOT):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "AI_RUNTIME")}
        return subprocess.run([sys.executable, "-I", STATE, "--root", root, "weight"] + list(args),
                              capture_output=True, text=True, env=env, check=False)

    def test_seven_lines(self):
        done = self.run_state("--files", "hooks/ai-path-guard.sh",
                              "--declare", "behaviour=1:changes an existing path, limited",
                              "--declare", "domain=0:no money", "--declare", "novelty=0:pattern exists")
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 7)
        self.assertTrue(re.match(r"^W 3 → guarded ", lines[-1]), lines[-1])

    def test_long_and_json(self):
        done = self.run_state("--files", "skills/ai-task/state.py,skills/ai-task/weight.py", "--long")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertLessEqual(len(done.stdout.splitlines()), 20)
        done = self.run_state("--files", "skills/ai-task/weight.py", "--json")
        data = json.loads(done.stdout)
        self.assertEqual(set(data["axes"]), set(weight.AXES))
        self.assertIn(data["mode"], ("light", "guarded", "full", "full_irreversible"))

    def test_refusals(self):
        self.assertEqual(self.run_state("--files", "a.py", "--declare", "domain=0").returncode, 1)
        self.assertEqual(self.run_state().returncode, 1)
        tree = Tree({"a.py": "x\n"})
        try:
            done = self.run_state("--mirror", root=tree.root)
            self.assertEqual(done.returncode, 1)
            self.assertIn("own table", done.stderr)
        finally:
            tree.close()

    def test_odd_input_is_refused_without_a_traceback(self):
        # Review L3: a 5000-digit declaration, a mirror onto a directory, a table of the wrong shape.
        done = self.run_state("--files", "a.py", "--declare", "scope=%s:x" % ("9" * 5000))
        self.assertEqual((done.returncode, "Traceback" in done.stderr), (1, False))
        tree = Tree({"a.py": "x\n"})
        try:
            policies = os.path.join(tree.root, ".ai", "policies")
            os.makedirs(os.path.join(policies, "weight.md"))
            with open(os.path.join(SHIPPED_DIR, "weight.json"), encoding="utf-8") as fh:
                table = json.load(fh)
            with open(os.path.join(policies, "weight.json"), "w", encoding="utf-8") as fh:
                json.dump(table, fh)
            done = self.run_state("--mirror", root=tree.root)
            self.assertEqual((done.returncode, "Traceback" in done.stderr), (1, False))
            self.assertEqual(sorted(os.listdir(policies)), ["weight.json", "weight.md"])
            table["axes"]["scope"]["bands"] = 5
            with open(os.path.join(policies, "weight.json"), "w", encoding="utf-8") as fh:
                json.dump(table, fh)
            done = self.run_state("--files", "a.py", root=tree.root)
            self.assertEqual((done.returncode, "Traceback" in done.stderr), (1, False))
            self.assertIn("malformed", done.stderr)
        finally:
            tree.close()

    def test_needs_no_task(self):
        tree = Tree({"a.py": "x\n"})
        try:
            done = self.run_state("--files", "a.py", root=tree.root)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse(os.path.exists(os.path.join(tree.root, ".ai", "state")))
        finally:
            tree.close()


if __name__ == "__main__":
    unittest.main()
