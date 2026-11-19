---
name: i-hate-spaghetti
description: Write and review code in any language that stays structured, quiet, and consistent with the codebase it lands in. Use when coding — by default on any task that writes, edits, refactors, or reviews code, adds a feature, or cleans up a mess. It learns the project's existing patterns first, keeps the diff small, and measures the result instead of praising it.
license: MIT
metadata:
  author: Chathula Sampath
  version: "1.0.0"
  repository: https://github.com/Chathula/i-hate-spaghetti
---

# i-hate-spaghetti

A code-quality contract for coding agents. It adds the one thing vibe-coding minimalism misses: **before** writing, the agent has to learn the codebase's own conventions; **after** writing, it has to measure what it produced.

**On by default for code.** Any task that touches code loads this skill without being asked. Say "stop spaghetti" or "normal mode" to turn it off for the session; it stays out of the way for prose, config-only edits, and questions.

Loaded once per task. Nothing here runs every turn.

## When to use

- Every task that creates, edits, moves or reviews code — feature, bugfix, refactor, review. This is the default, not an opt-in.
- Not for: prose, config-only edits, questions answered without touching code.

## The six laws

1. **Read before write.** Sniff the repo, then read every file your change touches plus the callers of every function you modify. Cheap exploration is a token tax you pay twice — once to look, once to be wrong.
2. **The project wins.** The existing pattern beats your taste, even when you'd do it differently. A shape that appears twice is the pattern; match it.
3. **One change, one reason.** No drive-by refactors inside a feature. Name the cleanup, let the user decide.
4. **Delete before you add.** Every new file, abstraction, flag and dependency must name the problem it solves *now*.
5. **Errors at the edges, types in the middle.** Validate at the boundaries, then trust your own data.
6. **Words are debt.** A comment that restates the code is a second copy that will drift. Match the project's comment register: a silent neighbourhood stays silent.

## Procedure

1. **Sniff.** `python3 scripts/spaghetti.py sniff .` — one command instead of ten file reads: stack, build/test/lint commands, layout, naming style, comment register, biggest files, commit style.
2. **Neighbourhood.** Read the files the change touches; search for the callers of everything you modify. Note the conventions you will follow — naming, error style, module boundaries, test location, comment density and form. Keep it silent, it is not a deliverable.
3. **Decide the shape before the code.** Where does this belong? Which existing module already owns this concept? Is there a helper for it? Only then write.
4. **Write** to the rules below.
5. **Score.** `python3 scripts/spaghetti.py score --diff` — every flag is debt you just added. Fix it, or say why not.
6. **Align.** Re-read only your added lines against the contract: naming, error style, comment register, test placement. Formatting your own diff is in scope; editing lines you did not write is not.
7. **Report** in four lines or fewer.

## Write-time rules

- **Naming** — reuse the project's word for a concept; never introduce a synonym. Name by what the thing *is*.
- **Functions** — one level of abstraction, ≤4 parameters (more means pass a struct), guard clauses instead of nesting.
- **Nesting** — max 3 levels. Deeper means extract or return early.
- **Modules** — one reason to change. Split by responsibility, never into one-function files.
- **Reuse** — the project's existing helper, component or type is the default; write a new one only when none exists and a second caller is already in sight. KISS and YAGNI are the tie-breakers; DRY starts at the third copy, not the second.
- **Duplication** — rule of three: the third occurrence gets extracted; the second is usually a coincidence.
- **State** — pure functions at the core, side effects at the edges. Anything that silently mutates is named for it or split.
- **Dependencies** — existing dependency > stdlib > new dependency. Never add a package for what ~20 lines do.
- **Abstractions** — none for a single implementation, no config for a value that never changes, no extension point before the second extension exists.
- **Tests** — non-trivial logic (a branch, a loop, a parser, a money or security path) leaves one runnable check behind, in the project's test location and style.
- **Comments** — match the register `sniff` reports. Sparse project: only why-comments, no narration. Documented project: the same doc format at the same boundaries. A comment the neighbours would not write is noise, however true.
- **Commits** — one logical change; the message says *why*, in the style the sniff shows.

## Noise rules

Delete on sight, in code you write *and* in code you touch:

- commented-out code, dead flags, unused imports and parameters, debug prints
- comments that restate the next line (`// increment counter`)
- `TODO` with no owner or condition — write `TODO(name): once X happens`
- layered error wrapping (`failed to save: failed to write: EACCES`) — wrap once, where it adds information
- placeholder names (`data`, `utils`, `helpers`, `manager`, `handle`, `process`) when something narrower exists
- try/catch that swallows

Keep comments that explain **why**: a non-obvious constraint, a workaround with a link, an API quirk, a deliberate tradeoff. If a simplification leaves a known ceiling, mark it in one line with the upgrade path.

## When the codebase's pattern is the problem

Common cases: a 900-line module, global mutable state, errors swallowed and logged, the same 20 lines copy-pasted six times, an abstraction that forces every change through five files.

- Do the task the existing way. Law 2 is not suspended because you are right.
- Raise it **once**, on one line at the end of the report:
  `pattern: <what> — <one-line cost> — fix: <one-line change>. Say the word.`
- Never refactor it unasked, never propose more than one. Code improved without being asked is code broken without being asked.

## Guardrails — never optimise these away

Input validation at trust boundaries · error handling that prevents data loss · security · accessibility · anything the user explicitly asked for · error messages a human has to act on. Smaller never means quieter about failure.

## Token discipline

- Do not re-read a file you already read this session; search for the symbol instead.
- Do not paste whole files into context to change ten lines.
- The diff is the deliverable. If your explanation is longer than the diff, delete the explanation.

## Modes

- **build** (default — on for every code task) — the rules above.
- **align** — the last pass over a finished change: `score --diff`, then reread only the added lines for naming, error style, comment register and test placement. Load when asked to align or tidy a diff after the fact; never reformat lines you did not write.
- **review** — load `references/review.md`; audits a diff or a repo and reports findings without editing.
- **off** — "stop spaghetti" / "normal mode".

## Files

All paths below are relative to **this skill's directory**, not the user's repo. Resolve them from the directory containing this `SKILL.md`.

- `references/smells.md` — symptom → cause → smallest fix. Load when a file feels wrong but you cannot name why.
- `references/patterns.md` — detecting conventions, matching them, proposing an upgrade without a rewrite.
- `references/review.md` — audit workflow and finding format.
- `scripts/spaghetti.py` — `sniff` and `score`. Heuristic: verify each flag, never obey it blindly.

## Report format

```
changed: <one line>
skipped: <what you deliberately left out>       (omit if nothing)
pattern: <existing-pattern issue + fix>          (omit unless real, max 1)
```

No code tours, no restating the diff, no "I have now improved…".
