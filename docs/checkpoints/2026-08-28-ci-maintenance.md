# 2026-08-28 — CI maintenance checkpoint

Tracking issue: [#22](https://github.com/umutseve4/enflasyonum/issues/22)

## Verified changes

- [PR #23](https://github.com/umutseve4/enflasyonum/pull/23) isolated EVDS discovery from ordinary PR validation while preserving its trusted `workflow_dispatch` path and corrected README status drift. Squash merge: `35f4dbc134b5cc75b8d54f2fb9504cf70b8f74b4`. Hosted CI run `33205939716` passed on Python 3.11, 3.12, and 3.13.
- [PR #20](https://github.com/umutseve4/enflasyonum/pull/20) upgraded `actions/setup-python@v5` to `@v7` in five workflows. Squash merge: `86e41695b8d204dea8ef804bb64f009d074d8ad0`. Hosted CI run `33206132150` passed on Python 3.11, 3.12, and 3.13.
- [PR #21](https://github.com/umutseve4/enflasyonum/pull/21) upgraded `actions/checkout@v4` to `@v7` in six workflows (`+6/-6`). Exact validated head: `1f74f4e963e16d566d3000e64ac8353c78e219f8`; hosted CI run `33206327029` passed with jobs `98968189118`, `98968188933`, and `98968189150`; independent QA verdict: PASS. Squash merge: `46acabe8ccdeff151a5abe9e5770669ac95b9fde` at `2026-08-28T20:02:41Z`.

## Hosted operational evidence

Automated live-ingest evidence commit `409187b4ef178783263c78b722b252417fca9916` recorded privacy-safe metadata in `artifacts/live-ingest.txt`: `run1=0`, `run2=0`; both results PASS; all 14 series processed 24 periods; headline table contained 24 rows over `2024-08-01 .. 2026-07-01`; `HEADLINE_LATEST_PERIOD=2026-07`; `HEADLINE_MOM_PCT=1.78`.

After PR #21 merged, hosted automation advanced `main` through `[skip ci]` evidence commits `6f30350e28fd38e0f5cd485ea3912d3cae506cc6` and `8758cfbd81101e46e8ed5720e8c450e32ab716dd`. These commits are operational evidence updates, not ordinary exact-SHA CI proof.

## Truth boundaries and remaining gate

- Manual EVDS discovery was not dispatched in this maintenance slice.
- Scheduled/manual workflow paths were not each independently exercised by the standard PR matrix.
- M1 remains open: its 14-distinct-real-use-day and first personal-inflation-result gate is not closed. The public usage count is not advanced without private evidence.
- M5 remains deferred until M1 closes.
- This checkpoint does not claim production readiness.

## Next action

Continue privacy-safe real use toward M1 closure; keep operational workflow evidence separate from the ordinary PR CI signal.