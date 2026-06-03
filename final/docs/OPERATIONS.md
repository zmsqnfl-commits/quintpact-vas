# VAS Operations Guide

This guide keeps routine maintenance decisions explicit so the system can be run and handed off without guesswork.

## Release Flow

1. Work in `src/`, `docs/`, `scripts/`, and tests.
2. Run the Python integrity tests.
3. Run the browser smoke test when Playwright is installed.
4. Sync release-ready files into `final/`.
5. Confirm `final/` matches the root working files before delivery.

## Verification Commands

```powershell
cd tests
python test_client_form.py
python test_html_syntax.py
python test_integrity_10loop.py
python run_10x_stress.py
npm run test:python
npm run test:browser
cd ..
```

`pytest` and Playwright are development dependencies. Install them only in a development environment. The broad Python integrity scripts are designed to be run directly because some of them exit intentionally after printing their own reports.

## Backup Policy

- `.vas_backups/`: keep the latest 10 root checkpoints.
- `.temp data/`: temporary agent workspace, safe to clear after handoff.
- `scripts/.vas_backups/`: script-local checkpoints, safe to clear after confirming root backups exist.
- `tests/__pycache__/` and `.pytest_cache/`: generated caches, safe to delete anytime.

## Failure Routing

- Architecture or file-boundary ambiguity goes back to Architect.
- Visual specification conflicts go back to Designer.
- Broken runtime behavior goes back to Implementer.
- Test failures go back to Implementer unless the test itself is demonstrably stale.
- Security or privacy concerns block final sync until Security signs off.
- After three repeated failures on the same issue, stop and ask the user for a decision.

## Git Hygiene

- Keep `.temp data/`, caches, Playwright reports, and backup archives untracked.
- Commit source, docs, scripts, tests, and final delivery files together when a release is cut.
- Use `git status --short` before and after every release sync.
