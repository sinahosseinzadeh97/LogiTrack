## Description

<!-- Summarize the change and the motivation behind it. Link any related issues. -->

Closes #<!-- issue number -->

---

## Type of Change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Refactor (no functional change — code structure, naming, performance)
- [ ] Documentation update
- [ ] CI / DevOps / infrastructure change
- [ ] Dependency update

---

## Changes Made

<!-- List the key files changed and what was done in each -->

| File | Change |
|------|--------|
| | |

---

## Testing

<!-- Describe how you tested this change -->

- [ ] Added / updated unit tests
- [ ] Added / updated integration tests
- [ ] Manually tested locally (describe below)
- [ ] No tests needed — explain why:

**Manual test steps:**
```
1.
2.
3.
```

**Test output / coverage:**
```
pytest tests/ --cov=app --cov=core --cov=ml --cov-fail-under=80
```

---

## Screenshots

<!-- For UI changes, attach before/after screenshots. Delete this section for backend-only PRs. -->

| Before | After |
|--------|-------|
| | |

---

## Checklist

- [ ] `ruff check .` passes (Python) or `npm run lint` passes (TypeScript)
- [ ] All existing tests pass
- [ ] Coverage is ≥ 80% (backend)
- [ ] New env vars are added to `.env.example` (if applicable)
- [ ] Database migrations are included and tested (if schema changed)
- [ ] API changes are reflected in OpenAPI — run `/docs` and verify
- [ ] Docker Compose still builds cleanly (`docker compose build`)

---

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path. Delete if not applicable. -->

**What breaks:**

**Migration steps for consumers:**

---

## Notes for Reviewer

<!-- Anything the reviewer should pay particular attention to, known edge cases, or design decisions made -->
