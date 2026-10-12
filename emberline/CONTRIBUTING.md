# Contributing

Emberline is an evidence desk. Patches that invent perimeters, forecasts, risk scores, or evacuation UX will be rejected.

## Setup

1. Fork and branch from `main`.
2. `cd backend && pip install -e ".[dev]" && pytest`
3. `cd frontend && npm install && npm test && npm run build`

## Rules

- Keep LIVE and SIM separated. Fail closed.
- Limitations belong on the brief, not only in a footer.
- Do not add a 0–100 score.
- Prefer tests that lock honesty (see `backend/tests/test_briefs.py`).
- Open a PR with the template checklist.

## Design partners

If you are a utility, municipal planning desk, MGA research, newsroom, or NGO wildfire desk, open an issue labeled `design-partner` rather than a feature dump.
