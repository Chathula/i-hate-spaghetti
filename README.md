# i-hate-spaghetti

**An agent skill that makes coding agents write code the next person can read — instead of code that merely runs.**

Works with Claude Code, Codex CLI, OpenCode, Pi, omp, and any agent that implements the [Agent Skills](https://agentskills.io) format.

```text
$ spaghetti.py sniff .
stack:  ts(412) css(31) py(12)
size:   455 source files, 61,204 lines, max depth 4
build:   bun
scripts: dev build test lint typecheck
lint:    eslint.config.js .prettierrc tsconfig.json
tests:   tests/ (dir, 88 files)
layout:  app components lib server scripts tests types
biggest: server/routes/reports.ts (912 lines)
         lib/api/client.ts (604 lines)
naming:  kebab-case (dominant); 5 samples
commits: feat(billing): add retry on capture | fix: quote order id | chore: bump deps
```

That is the whole point: **one command, ~30 lines, instead of ten exploratory file reads.** The agent learns the house style before it writes a line, and it pays for that knowledge in tokens once.

## Why

Generated code fails in three predictable ways, and none of them are "it doesn't work":

1. **It ignores the house style.** A second way to do what the codebase already does eleven times. Every future reader now holds two patterns.
2. **It is structurally accidental.** Logic lands wherever the cursor was: a 300-line handler, a `utils.ts` that owns nothing, three layers of try/catch around a missing null check.
3. **It is loud.** Comments restating the code, commented-out code, unused flags, `TODO`s, debug prints — noise that costs tokens every time the file is read.

Linters catch line-level style. Reviewers catch logic. Nobody catches "this file no longer belongs to this codebase" — until it is six months old. This skill makes the agent do it while it is cheap: at write time.

## How it works

Four rules, in order:

1. **Learn the project before writing.** `sniff` reports the stack, the build/test/lint commands, the layout, the dominant naming style, the biggest files (your future split candidates) and the commit-message convention.
2. **Read the neighbourhood.** The files the change touches, plus every caller of every function being modified. Missed callers are how a "small change" becomes a regression.
3. **Write the smallest coherent diff in the project's own pattern.** Not the smallest diff — the smallest *coherent* one. A guard in the shared function beats a guard in each of five callers.
4. **Measure the result.** `score` flags long files, long functions, deep nesting, duplicated blocks, commented-out code, TODOs and comment noise — per file, with line numbers. Exit code 1 when there is anything to look at, so it drops straight into a pre-commit hook or CI.

When the codebase's own pattern is the real problem (a 900-line module, swallowed errors, copy-paste everywhere), the agent does the task the existing way and **raises it once**, in one line, at the end. No unrequested refactors. Ever.

## Install

### One command, all agents

```bash
git clone https://github.com/Chathula/i-hate-spaghetti.git
cd i-hate-spaghetti
./install.sh                 # detects installed agents, installs for each
./install.sh --link          # symlink instead of copy (updates with git pull)
./install.sh --all           # install everywhere, even where detection is unsure
./install.sh --project ~/code/my-app   # install into that project only
```

### Where it lands

| Agent | User | Project |
|---|---|---|
| Claude Code | `~/.claude/skills/i-hate-spaghetti/` | `.claude/skills/…` |
| Codex CLI | `~/.codex/skills/i-hate-spaghetti/` | `.codex/skills/…` |
| OpenCode | `~/.config/opencode/skills/…` | `.opencode/skills/…` |
| Pi, omp, spec-compliant agents | `~/.agents/skills/…` | `.agents/skills/…` |

Manual install is one copy:

```bash
mkdir -p ~/.agents/skills && cp -r . ~/.agents/skills/i-hate-spaghetti
```

Codex CLI needs the skills feature enabled (`[features] skills = true` in `~/.codex/config.toml`); it also reads `.agents/skills`.
Claude Code, Codex and OpenCode all read `.agents/skills` too, so a single copy there covers most setups.

## Usage

The skill is model-invoked: write code as usual and it loads when the task touches code. To force it:

```text
Claude Code    /i-hate-spaghetti
Codex CLI      $i-hate-spaghetti   (or /skills)
OpenCode       skill: i-hate-spaghetti
Pi / omp       /skill:i-hate-spaghetti
```

Turn it off with **"stop spaghetti"** or **"normal mode"** in a message.

## The scripts, standalone

They are useful without any agent:

```bash
python3 scripts/spaghetti.py sniff .                    # project contract
python3 scripts/spaghetti.py score --diff               # only what you changed
python3 scripts/spaghetti.py score --max-lines 300 src  # stricter thresholds
```

Exit codes: `0` clean, `1` findings, `2` usage error — drop it in CI:

```yaml
- run: python3 scripts/spaghetti.py score --max-func 50
```

Python 3.8+, standard library only, no dependencies, no network. Findings are heuristics: they point at code worth a second look, they do not judge it.

`scripts/analysis.py` is the library half (walking, measuring); `scripts/spaghetti.py` is the CLI. Import the former if you want the checks inside your own tooling.

Known false positives, by design and by name:

- marker words (`TODO`, `FIXME`) inside regex literals or fixture strings — the line is still worth a glance
- JSX/markup nesting, which is a template tree rather than control flow — the depth limit doubles automatically for `.tsx/.jsx/.vue/.svelte/.html`
- brace counting on template languages where `{` is data, not scope

## Cost

| Loaded | When | Size |
|---|---|---|
| Description only | every turn, in the skill index | ~80 tokens |
| `SKILL.md` | when a coding task starts | ~1.65k tokens (106 lines) |
| `references/*.md` | only when the skill points at one | ~0.65–1.2k each |
| `sniff` output | once per repo, per task | ~0.3k tokens instead of ~3–8k of exploring |

That is the design constraint: **the skill must cost less than the exploration it replaces**, or nobody keeps it installed. Deep material lives in `references/` and is read on demand; the main file stays short enough to load on every task without hesitation.

## What it is not

- Not a linter, formatter, or replacement for either. If the repo has one, the skill defers to it.
- Not an auto-refactorer. It reports; the human decides.
- Not opinionated about your framework, language, or architecture — it takes its opinions from the repo it is standing in.
- Not a style police for code you did not touch. It governs the diff, not your weekend.

## Pairs well with

[ponytail](https://github.com/DietrichGebert/ponytail) answers *"does this need to exist?"* — the ladder, YAGNI, delete before add. **i-hate-spaghetti** answers *"now that it exists, does it belong?"* — structure, house style, and measured noise. Run both; they do not overlap.

## Contributing

Issues and PRs welcome. Rules for changes to the skill itself:

- Every rule added must be able to *change* what the agent writes. If it does not, it is prose, and prose costs tokens on every task.
- Prefer one new line in `references/smells.md` over a new section in `SKILL.md`.
- `python3 -m unittest discover -s tests` must pass, and `SKILL.md` must stay under 500 lines (the Agent Skills recommendation).

## License

MIT.
