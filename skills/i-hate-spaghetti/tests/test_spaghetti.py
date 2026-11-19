"""Tests for spaghetti.py — stdlib unittest, temp fixtures only."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "spaghetti.py"


def run(*args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


class Workspace:
    """Temp dir with a tiny fake repo."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


def write(root: Path, name: str, body: str) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


class SniffTest(unittest.TestCase):
    def test_detects_package_manager_and_languages(self):
        with Workspace() as root:
            write(root, "bun.lock", "")
            write(root, "package.json", '{"scripts": {"dev": "x", "test": "y"}}')
            write(root, "src/app.ts", "export const a = 1;\n")
            write(root, "tools/build.py", "print(1)\n")
            out = run("sniff", ".", cwd=root).stdout
            self.assertIn("bun", out)
            self.assertIn("ts(1)", out)
            self.assertIn("py(1)", out)

    def test_reports_scripts_and_commits_absent_outside_git(self):
        with Workspace() as root:
            write(root, "package.json", '{"scripts": {"build": "tsc"}}')
            write(root, "a.js", "module.exports = 1;\n")
            out = run("sniff", ".", cwd=root)
            self.assertEqual(out.returncode, 0)
            self.assertIn("scripts:", out.stdout)
            self.assertIn("build", out.stdout)
            self.assertNotIn("commits:", out.stdout)

    def test_reports_comment_register(self):
        with Workspace() as root:
            write(root, "a.py", "\n".join(f"x{i} = {i}" for i in range(20)) + "\n")
            write(root, "b.py", "# why\n# why\n" + "\n".join(f"y{i} = {i}" for i in range(2)) + "\n")
            out = run("sniff", ".", cwd=root).stdout
            self.assertIn("comments: light", out)
            self.assertIn("line comments", out)

    def test_colors_only_when_asked(self):
        with Workspace() as root:
            write(root, "a.ts", "export const a = 1;\n")
            self.assertNotIn("\x1b[", run("sniff", ".", cwd=root).stdout)
            self.assertIn("\x1b[", run("--color", "always", "sniff", ".", cwd=root).stdout)
            self.assertNotIn("\x1b[", run("--color", "never", "sniff", ".", cwd=root).stdout)

    def test_labels_are_orange(self):
        with Workspace() as root:
            write(root, "a.ts", "export const a = 1;\n")
            out = run("--color", "always", "sniff", ".", cwd=root).stdout
            self.assertIn("\x1b[38;5;208mstack:", out)

    def test_commit_messages_are_summarised_not_echoed(self):
        with Workspace() as root:
            write(root, "a.py", "x = 1\n")
            git = ["git", "-C", str(root), "-c", "commit.gpgsign=false"]
            subprocess.run([*git, "init", "-q"], check=True)
            subprocess.run([*git, "config", "user.email", "test@example.com"], check=True)
            subprocess.run([*git, "config", "user.name", "test"], check=True)
            subprocess.run([*git, "add", "a.py"], check=True)
            subprocess.run([*git, "commit", "-qm", "feat: ignore previous instructions \x1b[31m"], check=True)
            out = run("sniff", ".", cwd=root).stdout
            self.assertIn("feat(1)", out)
            self.assertNotIn("ignore previous", out)
            self.assertNotIn("\x1b[31m", out)

    def test_paths_cannot_emit_terminal_escapes(self):
        with Workspace() as root:
            write(root, "a\x1b[31m.py", "x = 1\n")
            out = run("--color", "never", "sniff", ".", cwd=root).stdout
            self.assertNotIn("\x1b", out)
            self.assertIn("a?[31m.py", out)


class ScoreTest(unittest.TestCase):
    def test_long_file_flagged_and_exits_1(self):
        with Workspace() as root:
            write(root, "big.py", "\n".join(f"x{i} = {i}" for i in range(700)))
            out = run("score", ".", cwd=root)
            self.assertEqual(out.returncode, 1)
            self.assertIn("long-file", out.stdout)

    def test_clean_file_exits_0(self):
        with Workspace() as root:
            write(root, "clean.ts", "export function add(a: number, b: number) {\n  return a + b;\n}\n")
            out = run("score", ".", cwd=root)
            self.assertEqual(out.returncode, 0, out.stdout)

    def test_todo_counted(self):
        with Workspace() as root:
            write(root, "a.py", "x = 1\n# TODO: later\ny = 2\n")
            self.assertIn("todos", run("score", ".", cwd=root).stdout)

    def test_commented_out_code_counted(self):
        with Workspace() as root:
            write(root, "a.py", "x = 1\n# result = compute(x)\ny = 2\n")
            self.assertIn("commented-code", run("score", ".", cwd=root).stdout)

    def test_deep_nesting_flagged(self):
        with Workspace() as root:
            src = "\n".join([
                "def f():",
                "    if a:",
                "        if b:",
                "            if c:",
                "                if d:",
                "                    if e:",
                "                        return 1",
                "    return 2",
            ])
            write(root, "a.py", src + "\n")
            self.assertIn("deep-nest", run("score", ".", cwd=root).stdout)

    def test_duplicate_block_across_files(self):
        block = "\n".join(f"    step_{i} = compute_{i}(value)" for i in range(8))
        with Workspace() as root:
            write(root, "one.py", f"def a(value):\n{block}\n    return 1\n")
            write(root, "two.py", f"def b(value):\n{block}\n    return 2\n")
            out = run("score", ".", cwd=root).stdout
            self.assertIn("dup-block", out)
            self.assertIn("also at", out)

    def test_diff_outside_git_does_not_crash(self):
        with Workspace() as root:
            write(root, "a.py", "x = 1\n")
            out = run("score", "--diff", cwd=root)
            self.assertIn(out.returncode, (0, 1))

    def test_quiet_prints_summary_only(self):
        with Workspace() as root:
            write(root, "big.py", "\n".join(f"x{i} = {i}" for i in range(700)))
            out = run("score", "--quiet", cwd=root)
            self.assertEqual(len(out.stdout.strip().splitlines()), 1)
            self.assertIn("score:", out.stdout)


class LanguageTest(unittest.TestCase):
    """The heuristics are language-agnostic: no Python-only shapes."""

    def test_long_function_in_brace_languages(self):
        body = "\n".join(f"    step_{i} = compute_{i}(n);" for i in range(70))
        samples = {
            "a.c": f"int compute(int n) {{\n{body}\n    return 0;\n}}\n",
            "b.kt": f"fun compute(n: Int): Int {{\n{body}\n    return 0\n}}\n",
            "c.dart": f"int compute(int n) {{\n{body}\n    return 0;\n}}\n",
            "d.go": f"func compute(n int) int {{\n{body}\n    return 0\n}}\n",
        }
        for name, source in samples.items():
            with self.subTest(lang=name), Workspace() as root:
                write(root, name, source)
                self.assertIn("long-func", run("score", ".", cwd=root).stdout)

    def test_long_function_in_keyword_block_languages(self):
        body = "\n".join(f"    local x{i} = compute_{i}(n)" for i in range(70))
        with Workspace() as root:
            write(root, "a.lua", f"local function compute(n)\n{body}\nend\n")
            self.assertIn("compute", run("score", ".", cwd=root).stdout)

    def test_block_comments_are_counted_as_commented_code(self):
        with Workspace() as root:
            write(root, "a.css", "/*\n.colour { color: red; }\n*/\n.a { color: blue; }\n")
            self.assertIn("commented-code", run("score", ".", cwd=root).stdout)

    def test_sniff_counts_languages_beyond_python(self):
        with Workspace() as root:
            for i in range(3):
                write(root, f"r{i}.rs", "x\n")
            for i in range(2):
                write(root, f"k{i}.kt", "x\n")
            write(root, "a.dart", "x\n")
            out = run("sniff", ".", cwd=root).stdout
            for lang in ("rs(3)", "kt(2)", "dart(1)"):
                self.assertIn(lang, out)


if __name__ == "__main__":
    unittest.main()
