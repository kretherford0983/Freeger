# What's new in 1.2.0 — quick guide

## Reports (menu: Reports)
**End of Year Audit** — choose the Fiscal Year, optionally one account, and whether VOID transactions are included.
*Open printable PDF* opens it in a new tab (print from there); *Download PDF* saves it. The PDF contains the budget,
a transaction index, then each transaction on its own page followed by all of its attachments, then the Fiscal Year
supporting documents. Page footers show the section and "Page X of Y".

**Entity activity** — choose an account (or all), a date range (or pick a Fiscal Year to fill the dates) and
optionally one entity; *Run report*. Expand a row for the individual transactions. *Print* or *Download CSV*.
Transfers between your own accounts are listed separately and are not included in the totals.

## Transfers (Register → Transfer…)
Pick the *To account*, amount, transaction date and (optionally) clear date. Two linked entries are created:
a withdrawal here ("Transfer to ******1234 for <organization>") and a deposit in the other account
("Transfer from ******6789 for <organization>"). Budgets are not affected. To fix a mistake, void either side —
both sides are voided — and enter the transfer again. Each side's clear date and notes can be edited separately.

## Finding entities faster
In *New transaction* start typing in the Payee/Entity box; the list filters as you type (name or ENT number).
Use ↑/↓ and Enter, or click.

## "No attachment will be provided"
Tick the box at the bottom of the transaction form when no document exists (e.g. interest paid directly by the bank).
A warning explains that transactions should normally have documentation; confirm to continue and optionally give a reason.
If you attach a document later, the mark is removed automatically.

## Documentation review
The Fiscal Year page lists transactions that are missing attachments or are marked "no attachment", and the same
counts appear in closure readiness (as warnings), on the dashboard and in the audit report. They never block
approval or closure. For split transactions: attaching a document to every allocation is always enough; a document
on the transaction itself counts only when at least one allocation also has one.
