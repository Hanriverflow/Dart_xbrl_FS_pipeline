# Credit Wedge

This project is not just a generic XBRL parser. The wedge is an evidence-backed issuer/credit analysis workflow that turns DART filings into a memo a human analyst can trust and reuse.

## Primary User

The primary user is a credit analyst or issuer analyst at a bank, brokerage, or research team. A secondary user is an internal finance or IR analyst who needs the same data for fast company review.

## Painful Job

The painful job is to answer, quickly and defensibly:

- How much debt is coming due?
- Is interest burden rising or falling?
- Are CAPEX and cash flow creating pressure?
- What do the notes say about FX exposure, borrowings, or other hidden risks?

A generic parser can extract text and tables. It does not reliably connect those facts into a decision-ready, traceable issuer view.

## Wedge

The wedge should be a single issuer/period analysis flow that produces a credit-style memo from the filing, with strong evidence links.

The first version should focus on:

- Borrowings and maturity pressure
- Interest expense and financing cost movement
- CAPEX versus operating cash flow
- FX sensitivity and other note-based risk signals

This is the sharpest story because it matches the repo’s strongest assets: batch processing, note table extraction, and evidence-first memo generation.

## Outputs That Make It Real

The wedge becomes tangible when one run produces all of the following:

- `reports/batch/<job_id>/summary.json`
- `reports/<rcept_no>_analysis.json`
- `reports/<rcept_no>_analysis.md`
- `reports/<rcept_no>_note_tables.json`
- `reports/<rcept_no>_profitability_memo.md`
- `reports/<rcept_no>_credit_memo.md`
- `reports/<rcept_no>_run_manifest.json`

These outputs show the full chain from filing to structured facts to an analyst-readable memo.

## Not In Scope

Keep these out of the wedge for now:

- General-purpose XBRL/taxonomy coverage for every filing shape
- Realtime or streaming analysis
- Web dashboards or BI-style exploration
- Full accounting coverage beyond the credit/issuer questions above
- A broad “analyze everything” product story

## Why This Wins

The value is not just extraction. It is speed plus trust.

- Speed: one batch job can process multiple issuers and periods.
- Trust: every claim in the memo can point back to a table, metric, or filing artifact.
- Repeatability: the same workflow can run again with the same artifact contract.

## Two-Week Path

Week 1:

- Pick one flagship issuer/period workflow and make it the default demo path.
- Ensure the CLI produces `analysis`, `note_tables`, `memo`, and `manifest` in one run.
- Make the memo explicitly highlight debt, interest, CAPEX, and FX risk.

Week 2:

- Add one credit-focused sample run to the repo docs with real output filenames.
- Tighten the README and quick start so the wedge is obvious in the first minute.
- Verify the wedge with a repeatable test run and keep the evidence in the repo.
