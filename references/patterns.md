# Patterns — learn the codebase, then match it

Loaded on demand, mostly at step 2 of the procedure, or when deciding whether to introduce something new.

## What "the pattern" actually is

A pattern is a **shape that repeats**, not a shape that exists once. Before you follow one, check the count: one occurrence is one author's opinion, two is a convention, five is the house style. Follow the count you measured, not the one you prefer.

Read in this order, and stop as soon as the answer is clear:

1. **The nearest sibling** — the file next to the one you are editing, doing the closest thing. This is where the convention you must match actually lives.
2. **The entry point** — `main`, a route handler, a CLI command. It shows how the project wires things: DI, globals, factories, singletons.
3. **One test file** — shows the naming, the assertion style, and, more usefully, how the authors expect things to be faked.

What to record (silently) from those three reads:

- **Naming** — file casing, function verb style (`getX` vs `fetchX` vs `findX`), boolean prefixes (`is`/`has`/`should`), the project's word for each domain concept.
- **Errors** — returned, thrown, `Result` types, error codes, custom error classes. Where do they get caught?
- **Boundaries** — where does validation happen? Where does I/O happen? Which layer talks to the database?
- **Tests** — directory, file naming, fixture style, mocks vs fakes.
- **Dependencies** — how new modules are pulled in: direct import, container, registry, barrel file.

## Matching without copying

- Copy the **shape**, not the content. If every handler is `export async function name(req, res) { const body = parse(req); ... }`, your handler starts with those two lines.
- Reuse the project's helper for the cross-cutting concern even if it is clunkier than what you would write. Two ways to do one thing is the start of the spaghetti.
- If no pattern exists for what you need, that is a real decision — not a licence. Say so in one line in the report (`new: <name> — no existing pattern, modelled on <sibling>`) so the choice is visible.

## When the pattern is bad

You will find existing code that is genuinely harmful. The order of operations:

1. **Do the task the existing way.** A consistent bad pattern costs less than two patterns.
2. **State the cost once, in the report.** One line, concrete: `pattern: every repo method builds its own SQL string — injection risk at 14 call sites — fix: move to the shared query builder in db/query.ts`.
3. **Offer the cheapest migration**, not the rewrite: the one-file change that reduces the next diff. "Strangler" it — new code uses the new path, old code converts when it is already being touched.
4. **Never start it unasked.** If the user says yes, that is now its own task with its own diff.

Proposals worth making: a shared helper for something copy-pasted 3+ times · a single error type at a boundary · type/struct for a validated primitive · one entry point replacing an init-order dance · a constraint moved into the schema.

Proposals not worth making: renaming things nobody shares · a framework swap · a rewrite of a working module · anything whose first step is "first, we change every file".

## Judging whether to introduce something new

Ask in this order; stop at the first yes:

1. Does the codebase already have this concept under another name? Search before answering.
2. Does an installed dependency solve it?
3. Does the standard library solve it?
4. Is it 20 lines in the module that owns the concept?
5. Only then: a new abstraction, and it names the second caller that will use it.

A new abstraction needs a second caller that exists **now**. "We will need it later" is how a codebase gets a `BaseEntityManagerFactory` nobody can delete.
