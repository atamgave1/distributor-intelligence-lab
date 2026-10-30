# Delivery gates

## Team

- AI analytics workstream: governed assistant, question evaluation and model limitations.
- Data platform workstream: incremental correctness, atomic publication, metadata and recovery.
- Analytics dashboard workstream: metric reconciliation, filters, presentation and AWS preparation.
- Integration lead: shared data, local runner, cross-project tests, review, release evidence and publication.

## Required local gates

1. Shared data regenerate deterministically and monetary totals reconcile.
2. Advertised assistant intents pass their question / correctness checks; unsupported requests abstain; user input cannot execute SQL.
3. Pipeline reruns do not double-count; invalid batches cannot replace valid published data; recovery is demonstrated.
4. Dashboard metrics reconcile, filters affect visible results, charts remain readable, and synthetic/local labels are visible.
5. Clean local startup succeeds, all required automated checks pass, documentation matches actual behavior, and public artifacts contain no credentials or client data.

## Deferred gates — not part of verified local completion

- Live LLM: configure an authorized provider and run the evaluation against the actual provider.
- Airbyte / Airflow / dbt / Superset: start and verify optional integrations; do not treat configuration files as execution evidence.
- AWS: agree region and budget; provision an isolated sandbox; execute Athena SQL; create and refresh QuickSight assets; inspect results; clean up.
- GitHub: publish under `atamgave1` using repository-local commit identity `atul <atul.tamgave@gmail.com>` after access is available. No global Git identity changes.
- Upwork: review final portfolio copy and evidence before uploading. No automatic client-result claims or account changes.

Verification output must distinguish passed, failed and deferred work. Timings must include environment and fixture size. No invented ROI, production-scale claims or SLA guarantees.
