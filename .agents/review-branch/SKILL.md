---
name: review-branch
description: >-
  Reviews the current git branch against its merge base (default main/master):
  runs the project test suite, then reports prioritized bugs (high/medium/low),
  refactor suggestions, test gaps, edge cases, and performance concerns. Use when
  the user asks for a branch review, code review of local changes, pre-merge review,
  or quality pass before a PR.
---

# Review branch

## Scope

1. **Identify the branch under review** — current `HEAD` unless the user names another ref.
2. **Choose a base** — prefer `origin/main`, then `main`, then `origin/master`, then `master`; if none exist, ask or use `git merge-base` with the remote default branch the user specifies.
3. **Collect changes** — `git diff <base>...HEAD` and `git log <base>..HEAD --oneline` (three-dot diff = merge-base aware).

## Always run tests first

Run the repo’s default test command **before** writing findings (adjust if the project uses something else):

- **uv**: `uv run pytest` (from repo root).
- **pip**: `pytest` after activating the venv.
- If tests fail, note failures under **High** priority and tie them to the failing modules.

Skip tests **only** if the user explicitly says so or if the environment cannot run them (then state what was skipped and why).

## Read enough code

For each changed file (and tight callees if behavior crosses modules), read the full surrounding context—not only the diff hunks—so reviews catch integration and API misuse.

## Output format

Use this structure (omit empty sections):

```markdown
## Branch review: `<branch>` vs `<base>`

### Tests
- Command run: …
- Result: pass | fail (summarize failures)

### Bugs (by priority)

#### High
- …

#### Medium
- …

#### Low
- …

### Refactor suggestions
- …

### Tests (coverage / gaps)
- Missing cases, weak assertions, flaky risks, e2e vs unit balance.

### Edge cases
- Null/empty inputs, concurrency, timeouts, error paths, boundary values, Cluster vs standalone if relevant.

### Performance
- Hot paths, N+1 / round-trips, unnecessary allocations, sync/blocking in async code, pipeline batching opportunities.

### Summary
- 2–4 bullets: ship/no-ship recommendation and blockers.
```

## Priority rubric

| Priority | Meaning |
|----------|---------|
| **High** | Wrong behavior, data loss/corruption risk, security issues, crashes, broken contracts, failing tests, race conditions that likely manifest |
| **Medium** | Likely bugs on uncommon paths, misleading APIs, incomplete error handling, maintainability hazards |
| **Low** | Style/nits, minor duplication, cosmetic naming, optional polish |

## Review dimensions (check explicitly)

- **Correctness** — logic, types, error handling, resource cleanup (`close`/`aclose`).
- **Security** — secrets, injection, unsafe deserialization, logging sensitive data.
- **Refactors** — smaller functions, clearer names, reduce duplication without changing behavior scope.
- **Tests** — behavior-changing diff should have tests; property-style edge cases where cheap.
- **Edge cases** — empty collections, `None`, TTL 0, cluster hash slots, decrypt/serialize failures.
- **Performance** — loops calling Redis per item where pipeline/`MGET` applies; crypto on hot paths.

## Notes

- Prefer **actionable** bullets with file paths and a short “why”.
- Do not rewrite the whole branch in the review; focus on material risk and clear improvements.
