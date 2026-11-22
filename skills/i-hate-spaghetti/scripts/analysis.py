"""Analysis half of i-hate-spaghetti: walk the tree, measure files, print nothing.

Every function here is a heuristic over text. Nothing imports the CLI, so the
module is usable from a script, a test, or an editor plugin.
"""
import json
import os
import re
import subprocess
import zlib
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "target", "vendor", ".venv", "venv",
    "__pycache__", "coverage", ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "Pods", ".gradle",
}
LANGS = {
    ".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".ts": "ts", ".tsx": "tsx",
    ".jsx": "jsx", ".go": "go", ".rs": "rs", ".java": "java", ".kt": "kt", ".kts": "kt",
    ".rb": "rb", ".php": "php", ".cs": "cs", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".cc": "cpp", ".hpp": "cpp", ".swift": "swift", ".dart": "dart", ".ex": "ex",
    ".exs": "ex", ".sh": "sh", ".bash": "sh", ".zsh": "sh", ".ps1": "ps1", ".sql": "sql",
    ".vue": "vue", ".svelte": "svelte", ".html": "html", ".css": "css", ".scss": "scss",
    ".sass": "scss", ".less": "scss", ".lua": "lua", ".zig": "zig", ".scala": "scala",
    ".clj": "clj", ".cljs": "clj", ".hs": "hs", ".ml": "ml", ".mli": "ml", ".fs": "fs",
    ".fsx": "fs", ".jl": "jl", ".r": "r", ".pl": "pl", ".pm": "pl", ".groovy": "groovy",
    ".sol": "sol", ".tf": "tf", ".hcl": "tf", ".nim": "nim", ".v": "v", ".sv": "v",
    ".asm": "asm", ".s": "asm", ".proto": "proto", ".graphql": "graphql", ".gql": "graphql",
    ".vb": "vb", ".bas": "vb", ".d": "d", ".cr": "cr", ".raku": "pl",
}
LINE_COMMENT = {
    "py": "#", "sh": "#", "rb": "#", "ex": "#", "pl": "#", "r": "#", "jl": "#",
    "nim": "#", "ps1": "#", "tf": "#", "clj": ";", "vb": "'",
    "lua": "--", "sql": "--", "hs": "--",
}
BLOCK_COMMENT = {
    "c": ("/*", "*/"), "cpp": ("/*", "*/"), "cs": ("/*", "*/"), "java": ("/*", "*/"),
    "kt": ("/*", "*/"), "scala": ("/*", "*/"), "swift": ("/*", "*/"), "dart": ("/*", "*/"),
    "js": ("/*", "*/"), "jsx": ("/*", "*/"), "ts": ("/*", "*/"), "tsx": ("/*", "*/"),
    "go": ("/*", "*/"), "rs": ("/*", "*/"), "php": ("/*", "*/"), "css": ("/*", "*/"),
    "scss": ("/*", "*/"), "sol": ("/*", "*/"), "groovy": ("/*", "*/"), "d": ("/*", "*/"),
    "cr": ("/*", "*/"), "vue": ("/*", "*/"), "svelte": ("/*", "*/"), "v": ("/*", "*/"),
    "ml": ("(*", "*)"), "fs": ("(*", "*)"), "tf": ("/*", "*/"), "ps1": ("<#", "#>"),
    "lua": ("--[[", "]]"), "jl": ("#=", "=#"), "nim": ("#[", "]#"),
    "html": ("<!--", "-->"),
}
COMMENT_DEFAULT = "//"
NO_LINE_COMMENT = {"css", "html"}
# Indentation-delimited blocks: Python/Ruby/Elixir, plus keyword-end languages whose
# bodies are still conventionally indented (Lua, Julia, Nim, Haskell, ML, F#, VB).
INDENT_LANGS = {"py", "rb", "ex", "lua", "jl", "nim", "hs", "ml", "fs", "vb"}
# Languages with no functions to measure: rules, markup, queries.
FUNC_LESS = {"css", "scss", "html", "sql", "asm", "proto", "graphql", "tf"}
MARKUP = {".tsx", ".jsx", ".vue", ".svelte", ".html"}
DUP_WINDOW = 8
CONTROL_WORDS = {
    "if", "for", "while", "switch", "catch", "with", "using", "lock", "foreach",
    "match", "do", "else", "try", "finally", "when", "return", "new", "throw",
    "await", "yield", "case", "assert", "sizeof", "typeof", "delete",
}
DECL_WORDS = {
    "function", "func", "fn", "fun", "def", "defp", "sub", "proc", "method",
    "constructor", "class", "struct", "interface", "enum", "trait", "impl",
    "namespace", "module", "object", "template",
}
NOT_NAMES = CONTROL_WORDS | DECL_WORDS
FUNC_KEYWORD = re.compile(
    r"\b(?:function|func|fn|fun|defp?|sub|proc|method|constructor)\s*\*?\s+"
    r"([A-Za-z_$][\w$]*)",
    re.I,
)
IDENT_PARENS = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")
ARROW_FUNC = re.compile(
    r"\b([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)
INDENT_DEF = re.compile(
    r"^(\s*)(?:(?:public|private|protected|internal|static|shared|local|export|async)\s+)*"
    r"(?:defp?|function|fun|func|fn|proc|method|sub)\s+"
    r"(?:self\.)?((?:[\w$]+[.:])?[\w$]+)",
    re.I,
)
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b", re.I)
CODE_ISH = re.compile(
    r"(;\s*$|=>|\{|\}|\(\)"
    r"|^\s*(?:if|for|while|return|const|let|var|import|from|def|"
    r"function|class|await|print|console)\b"
    r"|\b\w+\s*=\s*[^=\s]"
    r"|\b\w+\.\w+\()"
)


# ---------------------------------------------------------------- file walking

def is_source(path: Path) -> bool:
    return path.suffix.lower() in LANGS


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if is_source(p):
                yield p


@lru_cache(maxsize=8192)
def read_lines(path: Path):
    """Cached: one read per file per run, sniff and score both ask for it."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    if "\x00" in text[:1024]:
        return ()
    return tuple(text.splitlines())


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def clean(text, limit=200) -> str:
    """Untrusted display text: no terminal escapes, no unbounded line."""
    return CONTROL_CHARS.sub("?", str(text))[:limit]


def rel(path: Path, root: Path) -> str:
    try:
        return clean(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return clean(path)


def git(args, root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------- line-level helpers

def comment_token(path: Path) -> str:
    lang = LANGS.get(path.suffix.lower(), "")
    if lang in NO_LINE_COMMENT:
        return ""
    return LINE_COMMENT.get(lang, COMMENT_DEFAULT)


def block_comment(path: Path):
    return BLOCK_COMMENT.get(LANGS.get(path.suffix.lower(), ""))


def is_comment(line: str, token: str) -> bool:
    return bool(token) and line.lstrip().startswith(token)


def strip_inline(line: str, token: str) -> str:
    if not token:
        return line
    idx = line.find(token)
    return line if idx < 0 else line[:idx]


def _python_prose(lines):
    """Indices inside Python triple-quoted strings — prose, not structure."""
    inside, skip = None, set()
    for i, line in enumerate(lines):
        s = line.strip()
        if inside:
            skip.add(i)
            if inside in s:
                inside = None
            continue
        for q in ('"""', "'''"):
            if not s.startswith(q):
                continue
            skip.add(i)
            if s.count(q) == 1:
                inside = q
            break
    return skip


def _block_prose(lines, opening, closing):
    """Indices inside a multi-line block comment, for any language that has one."""
    inside, skip = False, set()
    for i, line in enumerate(lines):
        if inside:
            skip.add(i)
            if closing in line:
                inside = False
            continue
        start = line.find(opening)
        if start >= 0 and closing not in line[start + len(opening):]:
            inside = True
            skip.add(i)
    return skip


def prose_lines(path: Path, lines):
    """Lines that are prose (docstrings, block comments), not structure."""
    lang = LANGS.get(path.suffix.lower(), "")
    skip = _python_prose(lines) if lang == "py" else set()
    pair = BLOCK_COMMENT.get(lang)
    if pair:
        skip |= _block_prose(lines, *pair)
    return skip


def comment_bodies(path: Path, lines):
    """(line_index, text) for every line that is entirely a comment, line or block."""
    token = comment_token(path)
    pair = block_comment(path)
    inside = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if inside:
            yield i, s.split(pair[1], 1)[0]
            inside = pair[1] not in s
            continue
        if pair and pair[0] in s:
            head, rest = s.split(pair[0], 1)
            if not head.strip():
                yield i, rest.split(pair[1], 1)[0]
            inside = pair[1] not in rest
            continue
        if token and s.startswith(token):
            yield i, s[len(token):]


def comment_line_count(path: Path, lines, docstrings=True) -> int:
    """Comment lines, block comments included; Python docstrings on request."""
    count = sum(1 for _ in comment_bodies(path, lines))
    if docstrings and LANGS.get(path.suffix.lower()) == "py":
        count += len(prose_lines(path, lines))
    return count


def comment_style(files):
    """Comment register for sniff: density and the form the project writes."""
    total = comments = 0
    forms = Counter()
    for path in files:
        lines = read_lines(path)
        if not lines:
            continue
        total += sum(1 for line in lines if line.strip())
        comments += comment_line_count(path, lines)
        token = comment_token(path)
        pair = block_comment(path)
        for line in lines:
            s = line.lstrip()
            if s.startswith("/**") or s.startswith("///"):
                forms["doc blocks"] += 1
            elif path.suffix.lower() == ".py" and s.startswith(('"""', "'''")):
                forms["docstrings"] += 1
            elif token and s.startswith(token):
                forms["line comments"] += 1
            elif pair and s.startswith(pair[0]):
                forms["block comments"] += 1
    if not total:
        return "sparse (0%) · none"
    pct = round(100 * comments / total)
    density = "sparse" if pct < 5 else "light" if pct < 12 else "moderate" if pct < 25 else "heavy"
    styles = ", ".join(name for name, _ in forms.most_common(2)) or "none"
    return f"{density} ({pct}%) · {styles}"


def indent_unit(lines, token: str):
    for line in lines:
        if not line.strip() or is_comment(line, token):
            continue
        lead = len(line) - len(line.lstrip())
        if lead:
            return 4 if lead % 4 == 0 else (2 if lead % 2 == 0 else lead)
    return 4


# ------------------------------------------------------------------- measures

def max_nesting(path: Path, lines, skip=()):
    """(depth, line_no) — indentation for indent languages, braces otherwise."""
    lang = LANGS.get(path.suffix.lower(), "")
    token = comment_token(path)
    best = (0, 0)
    if lang in INDENT_LANGS:
        unit = indent_unit(lines, token) or 4
        for i, line in enumerate(lines, 1):
            if not line.strip() or i - 1 in skip or is_comment(line, token):
                continue
            depth = (len(line) - len(line.lstrip())) // max(unit, 1)
            if depth > best[0]:
                best = (depth, i)
        return best
    depth = 0
    for i, line in enumerate(lines, 1):
        if i - 1 in skip:
            continue
        s = strip_inline(line, token)
        if depth > best[0]:
            best = (depth, i)
        depth = max(depth + s.count("{") - s.count("}"), 0)
    return best


def function_lengths(path: Path, lines):
    """[(name, start_line, length)] — longest three, heuristic."""
    lang = LANGS.get(path.suffix.lower(), "")
    if lang in FUNC_LESS:
        return []
    if lang in INDENT_LANGS:
        return _indented_function_lengths(lines)
    return _brace_function_lengths(lines, comment_token(path))


def _indented_function_lengths(lines):
    out = []
    for i, line in enumerate(lines):
        match = INDENT_DEF.match(line)
        if match:
            base = len(match.group(1))
            out.append((match.group(2), i + 1, _indented_block_end(lines, i, base) - i))
    return sorted(out, key=lambda f: -f[2])[:3]


def _indented_block_end(lines, start, base):
    """First line at or left of `base` indentation after `start` — the block's end."""
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and len(line) - len(line.lstrip()) <= base:
            return i
    return len(lines)


def signature_name(code: str) -> str:
    """Name of the function/closure a brace-language line opens, or '' for control flow."""
    if "{" not in code:
        return ""
    head = code.split("{", 1)[0]
    words = re.findall(r"[A-Za-z_$][\w$]*", head)
    if words and words[0].lower() in CONTROL_WORDS:
        return ""
    match = FUNC_KEYWORD.search(head) or ARROW_FUNC.search(head)
    if match:
        return match.group(1)
    if "=" in head:
        return ""
    calls = [m for m in IDENT_PARENS.finditer(head) if m.group(1).lower() not in NOT_NAMES]
    return calls[-1].group(1) if calls else ""


def _brace_function_lengths(lines, token):
    depth, start, name = 0, None, ""
    out = []
    for i, line in enumerate(lines):
        code = strip_inline(line, token)
        if start is None:
            name = signature_name(code)
            if not name:
                continue
            start = i
        depth += code.count("{") - code.count("}")
        if depth <= 0:
            if i > start:
                out.append((name, start + 1, i - start))
            start = None
    if start is not None:
        out.append((name or "anonymous", start + 1, len(lines) - start))
    return sorted(out, key=lambda f: -f[2])[:3]


def commented_code(path: Path, lines) -> int:
    """Comment lines that look like code someone switched off — line or block."""
    return sum(
        1 for _, body in comment_bodies(path, lines)
        if len(body.strip()) > 3 and CODE_ISH.search(body)
    )


def dup_windows(path: Path, lines, skip=()):
    """(hash, start_line) for every DUP_WINDOW-line window of real code."""
    token = comment_token(path)
    norm = []
    for i, line in enumerate(lines, 1):
        if i - 1 in skip:
            continue
        s = line.strip()
        if not s or (token and s.startswith(token)) or s.startswith("#") or s.startswith("//"):
            continue
        norm.append((i, re.sub(r"\s+", " ", s)))
    for i in range(len(norm) - DUP_WINDOW + 1):
        body = "\n".join(x[1] for x in norm[i:i + DUP_WINDOW])
        yield zlib.crc32(body.encode()), norm[i][0]


def scan_file(path: Path, max_lines=400, max_func=60, max_nest=4):
    """[(line, check, detail)] for one file. Empty list means it looks fine."""
    lines = read_lines(path)
    if not lines:
        return []
    skip = prose_lines(path, lines)
    total = len(lines)
    findings = []

    if total > max_lines:
        findings.append((1, "long-file", f"{total} lines (max {max_lines})"))

    for name, start, length in function_lengths(path, lines):
        if length > max_func:
            findings.append((start, "long-func", f"{name} {length} lines"))
            break

    depth, at = max_nesting(path, lines, skip)
    # JSX/markup nesting is a template tree, not control flow — allow twice the depth.
    limit = max_nest * 2 if path.suffix.lower() in MARKUP else max_nest
    if depth > limit:
        findings.append((at, "deep-nest", f"depth {depth} (max {limit})"))

    dead = commented_code(path, lines)
    if dead:
        findings.append((1, "commented-code", f"{dead} lines"))

    todos = sum(1 for line in lines if TODO_RE.search(line))
    if todos:
        findings.append((1, "todos", f"{todos} markers"))

    long_lines = sum(1 for i, line in enumerate(lines) if len(line) > 120 and i not in skip)
    if long_lines:
        findings.append((1, "long-lines", f"{long_lines} lines >120"))

    nonblank = sum(1 for line in lines if line.strip())
    comments = comment_line_count(path, lines, docstrings=False)
    if total >= 50 and nonblank and comments / nonblank > 0.40:
        findings.append((1, "noise-ratio", f"{round(100 * comments / nonblank)}% comments"))

    return findings


def duplicate_findings(targets, root: Path, limit=5):
    """[(path, line, check, detail)] for blocks repeated across the scanned set."""
    windows = defaultdict(list)
    for p in targets:
        lines = read_lines(p)
        for h, line in dup_windows(p, lines, prose_lines(p, lines)):
            windows[h].append((p, line))

    found, seen = [], set()
    for hits in windows.values():
        found.extend(_hits_for_block(hits, root, seen, limit - len(found)))
        if len(found) >= limit:
            break
    return found


def _hits_for_block(hits, root: Path, seen, room):
    """One report per file for a repeated block, at most `room` of them."""
    if len({str(p) for p, _ in hits}) < 2:
        return []
    out = []
    for (p, line), (other, other_line) in zip(hits, hits[1:]):
        if len(out) >= room:
            break
        if str(p) in seen:
            continue
        seen.add(str(p))
        detail = f"{DUP_WINDOW}-line block also at {rel(other, root)}:{other_line}"
        out.append((p, line, "dup-block", detail))
    return out


# ------------------------------------------------------------- project shape

def detect_package_managers(root: Path):
    found = []
    manifest = (
        ("bun.lockb", "bun"), ("bun.lock", "bun"), ("package-lock.json", "npm"),
        ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("pyproject.toml", "pyproject"),
        ("requirements.txt", "pip"), ("Cargo.toml", "cargo"), ("go.mod", "go"),
        ("Makefile", "make"), ("docker-compose.yml", "compose"), ("docker-compose.yaml", "compose"),
    )
    for name, label in manifest:
        if (root / name).exists() and label not in found:
            found.append(label)
    return found


def package_scripts(root: Path):
    pkg = root / "package.json"
    if not pkg.exists():
        return []
    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    return list(data.get("scripts", {}).keys())[:12]


def lint_configs(root: Path):
    names = (
        ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.cjs",
        "eslint.config.js", "eslint.config.mjs", "eslint.config.ts", "biome.json",
        ".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js",
        "ruff.toml", ".flake8", "setup.cfg", ".golangci.yml", "rustfmt.toml",
        ".editorconfig", "tsconfig.json", ".stylelintrc", ".stylelintrc.json",
    )
    return [n for n in names if (root / n).exists()]


def test_locations(root: Path):
    found = []
    for name in ("tests", "test", "__tests__", "spec"):
        d = root / name
        if d.is_dir():
            found.append(f"{name}/ (dir, {sum(1 for f in d.rglob('*') if f.is_file())} files)")
    by_name = sum(
        1 for p in walk(root)
        if p.name.endswith("_test.go") or p.name.startswith("test_")
        or ".test." in p.name or ".spec." in p.name
    )
    if by_name:
        found.append(f"{by_name} test files by name")
    return found[:4]


def commit_style(subjects):
    """Commit register from prefixes only; never echo the messages."""
    kinds = Counter(s.split(":", 1)[0] for s in subjects if ":" in s)
    if not kinds:
        return f"{len(subjects)} recent, no prefix convention"
    return " ".join(f"{clean(name, 24)}({count})" for name, count in kinds.most_common(3))


def naming_style(names):
    if not names:
        return "unknown"
    kinds = Counter()
    for name in names:
        stem = name.rsplit(".", 1)[0]
        if "-" in stem and "_" not in stem:
            kinds["kebab-case"] += 1
        elif "_" in stem and "-" not in stem:
            kinds["snake_case"] += 1
        elif stem[:1].isupper():
            kinds["PascalCase"] += 1
        elif any(c.isupper() for c in stem):
            kinds["camelCase"] += 1
        else:
            kinds["flat"] += 1
    top, count = kinds.most_common(1)[0]
    return top if count > len(names) / 2 else "mixed"
