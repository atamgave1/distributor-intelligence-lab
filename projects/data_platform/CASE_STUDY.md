# Portfolio case study: reliable sales data for a fictional distributor

**Disclosure:** Independent demonstration using 100% synthetic data. The business, records and implementation are a portfolio scenario. No client data or client performance claims are included.

## Business problem

A growing distributor needs consistent sales and margin reporting despite returns, corrections, delayed records and failed refreshes. The demonstration asks: can a reporting pipeline update facts without double-counting revenue and keep the last valid report available when a refresh fails?

## My contribution in this demonstration

Designed and implemented a local source-to-raw-to-warehouse pipeline, a shared-data adapter, transactional publication, cursor state, validation checks and failure-recovery tests. Documented metric semantics and operational limits so a reviewer can reproduce the behavior.

## Solution

- Consume the shared synthetic distributor's signed sales/returns ledger.
- Store raw events separately from the reporting warehouse.
- Validate data before publishing detail and daily sales/margin marts.
- Use upserts, timestamp overlap and tombstones for the mutable-source test scenario.
- Commit raw changes, published marts and cursor state together.
- Record both successful and failed attempts.

## Observed outcomes

The current measured test count and reconciliation totals are recorded in `evidence/verification.json`, with the source dataset hash and actual unit test output. The tests prove retries do not duplicate facts, late changes within the configured overlap are captured, invalid input is rejected, and injected failures preserve the previous publication and cursor. The shared-source detail and daily totals reconcile to source queries.

These observations are local demonstration results, not client savings or production guarantees. The shared immutable fixture is read as a full snapshot; incremental behavior is exercised separately against a mutable synthetic source. Airbyte, Airflow, dbt, Redshift and Superset have not been executed in this build.

## Suggested screenshots and walkthrough

1. Architecture diagram plus the explicit synthetic-data disclosure.
2. Successful CLI output and annual source/detail reconciliation evidence.
3. Automated tests showing injected failures followed by successful retries.
4. A read-only view of the published daily sales/margin mart.

Walkthrough: describe the business question, explain the distinction between static and mutable modes, demonstrate a failed refresh preserving the prior totals, rerun successfully, and finish with reconciliation and known limitations. Do not use unrelated client screenshots.
