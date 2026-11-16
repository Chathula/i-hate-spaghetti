# Smells — symptom → cause → smallest fix

Loaded on demand. Each entry is a decision, not a lecture: if the symptom is there, the fix column is the cheapest thing that removes it. Verify before acting — these are heuristics, and a false positive that starts a refactor is worse than the smell.

## Functions

- **Long function (>60 lines)** — cause: several abstractions living in one body (fetch + transform + validate + format + persist). Fix: cut at the natural blank lines; each cut gets a name that says *what*, not *how*. Never extract a function whose name is a restatement of its body.
- **Boolean parameter** (`render(true, false)`) — cause: two behaviours in one function. Fix: split into two named functions, or take an options object if the combinations are genuinely independent. Boolean blindness is a reading cost paid at every call site.
- **Flag argument used in one branch** — cause: configuration where code would do. Fix: delete the flag and the dead branch with it.
- **5+ parameters** — cause: passing fields, not a concept. Fix: group the parameters that always travel together into the struct that already exists in the domain.
- **Output parameter** (`def parse(s, out)`) — cause: avoiding a return value. Fix: return it.
- **Deep nesting (>3)** — cause: early exits written as else-branches. Fix: guard clause at the top of the block; the happy path stays at one indent.

## Modules and layers

- **God module** — one file every change touches. Cause: no ownership boundaries; unrelated concerns accreted. Fix: split along the *import* seams you can already see (what imports it, what it imports), not by line count.
- **Utils / helpers dumping ground** — cause: naming a file after anonymity. Fix: move each function to the module that owns the concept. The file disappearing is the success condition.
- **One-function file** — cause: abstraction by file system. Fix: inline it, unless the file is a genuine boundary (a port, an entry point).
- **Circular imports** — cause: two modules that each own half of one concept. Fix: extract the shared half into a third module both depend on.
- **Shotgun surgery** — one concept change touches 5 files. Cause: the concept was never given a home. Fix: give it one module and let the callers route through it (this is also the lazy fix — it shrinks every future diff).

## Data and state

- **Primitive obsession** (`str` for user id, `dict` for row) — cause: no type for the concept. Fix: name the concept once. Do this only when it is already being validated in three places.
- **Global mutable state** — cause: convenience at the first call site, pain at every later one. Fix: pass it, or scope it to the request/job. Do not "clean this up" unasked.
- **Temporal coupling** (`init()` must run before `process()`) — cause: hidden order. Fix: one entry point that does both, or return the thing `init` produces instead of storing it.
- **Hidden side effect** — a getter that writes, a constructor that does I/O. Fix: move the effect to the edge, and name the function for the effect if it stays.

## Duplication

- **Copy-paste block, 2 occurrences** — leave it. Rule of three; two is often coincidence and the wrong abstraction is worse than the copy.
- **Copy-paste block, 3+ occurrences** — extract, but extract the *stable* part only. If the copies differ in one line each, the shared parameter is the varying part.
- **Same logic, different shape** (a `for` loop and a `map` doing the same transform) — cause: two authors, two eras. Fix: keep the one that matches the rest of the file.

## Errors

- **Swallowed catch** — `catch { log(e) }` with no rethrow, no state change, no user signal. Cause: making the type checker happy. Fix: rethrow, or handle — do one.
- **Layered wrapping** — `failed to X: failed to Y: EACCES`. Fix: wrap once, at the layer that adds information a caller cannot get elsewhere.
- **Sentinel returns** (`null`, `-1`, empty string meaning "not found") — cause: avoiding an error type. Fix: at a trust boundary, return an explicit result; deep inside, return the optional and let the caller decide.
- **Catch all at the top** — `try { main() } catch { panic }`. Acceptable only at process entry, and it must still exit non-zero.

## Noise

- **Comment restating code** — delete. The code is the source; the comment is a copy that will drift.
- **Commented-out code** — delete. Git remembers it; the comment only makes every future reader evaluate dead text.
- **`TODO` with no owner** — either do it now, or `TODO(name): condition to act`.
- **Placeholder names** — `data`, `tmp`, `result`, `item`, `info`. Rename to what it holds. This is the cheapest readability win in the file.
- **Dead flag** — a config value read but never branched on. Delete it and its docs entry.
