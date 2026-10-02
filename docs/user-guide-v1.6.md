# What's new in 1.6 — quick guide

*1.6.0: the optional Fundraiser module (core). 1.6.1: buckets, cash float, exclusions and fundraiser documents.
1.6.2: the fundraiser report. A later 1.6 release adds reminders.*

## Turning the module on (Administrator)
System/About → **Optional modules** → tick **Fundraiser module**. Budget Managers, Budget Users, Register Users and
Auditors then see **Fundraisers** in the menu (after their next sign-in or page reload). Turning it off hides the
module; nothing is deleted.

## Setting up a fundraiser (Budget Manager)
Set it up as soon as it is agreed — even a year ahead.
1. Fundraisers → **New fundraiser**: name, description and the **event date(s)** (the day or days the event takes
   place; leave the end date empty for a one-day event).
2. **Budgets:** pick the income and/or expense budget. You can choose from a Fiscal Year that is set up and open
   when the event is inside it or within **3 months** of its start or end — so a January event can use this year's
   budget for the preparation and next year's for the event. At most two Fiscal Years, one income and one expense
   budget each. If next year is not set up yet, save now and come back to add its budget once it exists (Draft is
   enough). Choosing a parent budget includes all its sub-budgets; choosing an "Other" budget may mix in unrelated
   items — the form warns about both.
3. **Description filter (optional):** only lines whose description contains this text count (any case). Tick
   *Advanced* to use a regular expression. The form shows how many lines will be included.

Everything allocated to the chosen budgets counts — purchases before the event and deposits after it included.
Transactions are always entered in the Register as usual.

## Viewing a fundraiser (everyone with access)
Choose the Fiscal Year (or *Upcoming — no Fiscal Year yet*) and open a fundraiser: income, expenses, net and the
return on expenses, a breakdown per Fiscal Year, charts, every included transaction (the account links to the
Register) and the transactions' attachments. Notices remind you, for example, to select next year's budget.

## Managing a fundraiser (1.6.1 — Budget Managers and Register Users)
- **Buckets:** in the *Buckets* section click **New bucket** (e.g. *Food sales*, *Raffle*). In the transaction list
  click **Manage** on a line and enter the amount for each bucket (**All remaining** fills in what is left). One
  deposit can be split across several buckets. Each bucket shows its income, expenses and net.
- **Cash float:** on the withdrawal that took cash out for the cash box, click **Manage** → tick **Cash float out**
  and enter the amount. On the deposit that brought it back, tick **Cash float returned** and enter the float amount
  (e.g. 200 of a 1,450 deposit). Those amounts no longer count as fundraiser expenses or income.
- **Exclude a line:** **Manage** → *Exclude this line from the fundraiser* and give a reason. The transaction itself
  is unchanged in the Register.
- **Fundraiser documents:** add flyers, permits or tally sheets under *Fundraiser documents*.
- Lines in a closed Fiscal Year can no longer be changed.

## Fundraiser report (1.6.2)
- **Report (PDF)** on a fundraiser's page prints the whole fundraiser: figures, buckets, every transaction line,
  excluded lines, and the documents and attachments themselves.
- Reports → **End of Year Audit** and **Fiscal Year Close**: *Include fundraisers* (ticked by default) adds the same
  section for every fundraiser of that Fiscal Year (not archived), after the transactions and before the signature
  page. A fundraiser that spans two Fiscal Years appears complete in both years' reports.

## Archive or delete
**Archive** hides a finished fundraiser from the list (tick *Show archived* to see it). **Delete** removes a
fundraiser's settings (never transactions); it is not possible once one of its Fiscal Years is closed or while it
has buckets, cash-float marks, exclusions or documents.
