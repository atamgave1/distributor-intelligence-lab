# Portfolio presentation

Use three distinct entries linked to the same reproducible demonstration repository. Each entry must explicitly say **independent demonstration using synthetic data**. Do not label these as anonymized client implementations, because they were built from public business problems rather than client source material.

## 1. Governed Analytics Assistant for Distributor Profitability

**Problem:** finance and operations users need consistent answers about revenue, margins and working capital without manually rebuilding reports.

**Demonstration:** a local analytics assistant with defined metric semantics, bounded query capabilities, tables, and a transparent distinction between the deterministic demonstration and any optional live model.

**Evidence to attach:** question / answer screenshot, metric provenance, evaluation report, architecture, and documented limitations. Describe only the capabilities actually implemented and tested. Do not claim forecasting or predictive accuracy unless the relevant evaluation is included.

## 2. Reliable Incremental Sales Data Pipeline

**Problem:** retries, late source updates and failed refreshes can corrupt reporting or double-count business activity.

**Demonstration:** validated incremental ingestion with stable keys, repeatable transformations, atomic publication, run records, and deliberate failure / recovery tests.

**Evidence to attach:** successful run and failure-recovery output, model diagram, reconciliation checks, setup instructions and execution boundaries for optional orchestration / warehouse adapters.

## 3. Distributor Profitability & Receivables Dashboard

**Problem:** leaders need visibility into profitable growth, customer concentration, and overdue balances.

**Demonstration:** interactive local reporting over synthetic sales and payments with explicit metric definitions and date / business filters. AWS deployment assets are preparation only until actually executed.

**Evidence to attach:** executive, customer/product, and receivables screenshots; filter example; KPI reconciliation; AWS migration notes. Use the title “AWS Athena & QuickSight” only after successful deployment and actual cloud screenshots.

## Claims checklist

- Attribute public case studies to their publishers; never imply involvement in their projects.
- State individual contribution as building this demonstration.
- Use measured technical results from verification, not invented client savings.
- Do not reuse the wording of client reviews to imply these new demonstrations were commissioned by those clients.
- Keep pending integrations visible in README and case study copy.
