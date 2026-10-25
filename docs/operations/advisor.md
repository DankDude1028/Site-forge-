# Opus 5.5 checkpoint advisor

The advisor sends a small number of checkpoint reviews to Claude Opus 5.5
(`claude-opus-5-5`) where local models are weakest: a site review before
publication, and a research check before a niche is approved. Local models still
do the bulk of the work. Every review is a paid `spend_money` action under the
normal policy engine.

**Status:** fake-client tests pass. One owner-approved live site review on
2026-10-22 cost **$0.098124**: 7,356 input and 3,435 output tokens, against a
$0.833299 authorization. It was served by Opus 5.5 with no fallback and returned
schema-valid findings. That run is a pipeline check, not a quality benchmark.

## Safety properties

- **Off by default.** `SITEFORGE_ADVISOR_ENABLED=false`; the external spend default stays $0.
- **Owner approval per review.** `advisor propose` writes the exact request to
  `runtime/advisor/<sha256>.request.json` and files an approval bound to that hash and
  its worst-case cost. Nothing is sent until the owner approves it on the dashboard
  Approvals page. A changed file no longer matches its approval.
- **Caps.** Authorization reserves the worst case against the current day's and month's
  USD budgets. `SITEFORGE_ADVISOR_DAILY_USD` and `SITEFORGE_ADVISOR_MONTHLY_USD`
  only create missing budget rows; they never raise an existing limit. These are
  organization-wide external-spend budgets, not advisor-only budgets. The kill switch
  blocks reviews.
- **Worst-case bound.** The reservation covers the full `max_tokens` output on
  Opus 5.5 and on the refusal fallback (`claude-opus-4-8`, priced higher), with input
  charged at the cache-write rate. A free `count_tokens` call must stay within the
  approved input bound, or nothing is sent and the reservation is released.
- **Sent once.** SDK retries are disabled. A lost connection leaves the receipt
  `unknown` with its reservation held, and the review is never re-sent. Reconcile it
  from provider usage instead. An HTTP error response releases the reservation.
- **Measured booking.** Reconciliation books the cost of each attempt in
  `usage.iterations` at that model's list price (`RATES` in `siteforge/advisor.py`,
  version `anthropic-list-2026-10-22`). A cost above the approval would still be
  booked and flagged in the audit trail.
- **What leaves the PC.** Only the brief, the named text files and the PNG
  screenshots you pass. Inputs that look like credentials are refused before approval.
  Findings are untrusted input for a human decision, never instructions.

## Use

1. Put `ANTHROPIC_API_KEY` in the ignored `.env` file yourself, and set
   `SITEFORGE_ADVISOR_ENABLED=true` along with the two cap values.
2. Prepare a review. This sends nothing:

   ```powershell
   .\.venv\Scripts\python.exe -m siteforge.cli advisor propose --kind site-review --site-id <site-uuid> `
     --brief brief.md --text home.txt --screenshot home-desktop.png --screenshot home-mobile.png
   ```

3. Approve the printed approval on the dashboard Approvals page after checking its
   summary and worst-case amount.
4. Send it:

   ```powershell
   .\.venv\Scripts\python.exe -m siteforge.cli advisor run --approval-id <id> --request <request-path>
   ```

   The result, with findings, design direction, the model that served it and the
   measured cost, is written to `runtime/advisor/<sha256>.result.json`.

Research checks use `--kind research-check` with the evidence packet passed as
`--text`; screenshots are refused for that kind.

## Limits

- The QA and research agents do not call the advisor automatically. Reviews are
  started by the owner.
- Screenshot capture is not automated; pass PNG files captured with Playwright or a
  browser.
- Prices are recorded constants. Re-check them against Anthropic's pricing page before
  relying on the bound, and update `RATES_VERSION` when they change.
- The advisor has not been qualified on the local 100-task benchmark. That run costs
  money and needs its own approval.
