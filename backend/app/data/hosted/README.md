# Public historical demo release

This directory contains eight attributed public historical case snapshots, their cached chronological evaluations, six separate generated benchmark fixtures and the required NAB license notice. It contains no user-uploaded documents, API credentials, private session exports or database backups.

`manifest.json` records the method version, included case IDs, file sizes and SHA-256 checksums. The API checks this manifest before starting in `HOSTING_PROFILE=free_demo`. Every case also verifies its own canonical dataset hash. Source response hashes, retrieval timestamps, provenance URLs, missing observations and native sampling intervals remain in the case snapshots.

Cached evaluation is retrospective. Event-window proxies differ from independent annotations, warning metrics with too few event onsets remain limited, and geographic/context series do not establish operational impact or causation. See the case-specific limitations and `docs/HISTORICAL_DATA.md` and `docs/HISTORICAL_RESULTS.md` at the repository root.

Rebuild this package only after downloading and evaluating all public cases in the full local workspace:

```bash
python -m app.historical_cli download --all
python -m app.historical_cli evaluate --all
python -m app.prepare_hosted_data
```

Run these commands from `backend` with the local artifact cache configured. The preparation tool copies only the approved cases/evaluations, license notice and generated benchmark data, never the entire artifact directory.
