// E2E UI verification (AC-INIT-*, AC-UI-THEME-*, AC-FY-VIS-*, AC-SEC-005/011, AC-AUTH-SELF-001, AC-REG-001).
import { expect, test, type Page } from "@playwright/test";

const PW = "Correct-Horse-9-Battery";
test.describe.configure({ mode: "serial" });

async function login(page: Page, user: string, pw = PW) {
  await page.goto("/");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(pw);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
}

async function createUser(page: Page, username: string, roleLabel: string) {
  await page.goto("/users");
  await page.getByRole("button", { name: "New user" }).click();
  const dlg = page.getByRole("dialog");
  await dlg.getByLabel("Username").fill(username);
  await dlg.getByLabel("Email").fill(`${username}@example.org`);
  await dlg.getByLabel("Initial password").fill(PW);
  await dlg.getByLabel("FINANCIAL").check();
  await dlg.getByLabel(roleLabel).check();
  await dlg.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("cell", { name: username, exact: true })).toBeVisible();
}

test("AC-INIT-001..007: fresh install wizard bootstraps a working Administrator", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Initialization Wizard" })).toBeVisible();
  await page.getByLabel("Organization / Workspace Name").fill("E2E Org");
  await page.getByLabel("Administrator Username").fill("admin");
  await page.getByLabel("Administrator Email Address").fill("admin@example.org");
  await page.getByLabel("Password", { exact: true }).fill(PW);
  await page.getByLabel("Password Confirmation").fill(PW);
  await page.getByRole("button", { name: "Initialize" }).click();
  await expect(page.getByRole("heading", { name: "Administration" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link")).toHaveText(["Dashboard", "Users", "Audit Log", "System/About"]);
  await nav.getByRole("link", { name: "Users" }).click();
  const row = page.getByRole("row", { name: /admin/ });
  await expect(row).toContainText("ADMINISTRATOR");
  await expect(row).toContainText("admin@example.org");
  await nav.getByRole("link", { name: "Audit Log" }).click();
  await expect(page.getByText("SYSTEM_INITIALIZED")).toBeVisible();
  await page.goto("/fiscal-years");
  await expect(page.getByText("You are not authorized to view this module.")).toBeVisible();
  await createUser(page, "bm1", "Budget Manager");
  await createUser(page, "ru1", "Register User");
  await logout(page);
  await login(page, "admin");
  await expect(page.getByRole("heading", { name: "Administration" })).toBeVisible();
});

test("AC-UI-THEME-001..003: dark mode persists across logout/login", async ({ page }) => {
  await login(page, "bm1");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: /Switch to dark mode/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "Fiscal Years" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await logout(page);
  await login(page, "bm1");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).not.toBe("rgb(246, 247, 249)");
});

test("AC-FY-VIS-001..007 + AC-BUD: Budget Manager creates Draft FY, budget, institution and account", async ({ page }) => {
  await login(page, "bm1");
  await page.getByRole("link", { name: "Fiscal Years" }).click();
  await page.getByRole("button", { name: "New Fiscal Year" }).click();
  const dlg = page.getByRole("dialog");
  await dlg.getByLabel("Identifier").fill("2027");
  await dlg.getByLabel("Start date").fill("2026-07-01");
  await dlg.getByLabel("End date").fill("2027-06-30");
  await dlg.getByRole("button", { name: "Create Fiscal Year" }).click();
  await expect(page.getByRole("heading", { name: /FY2027/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /FY2027/ })).toContainText("Draft");
  await page.getByRole("link", { name: "← Fiscal Years" }).click();
  await expect(page.getByRole("link", { name: "FY2027" })).toBeVisible();
  await page.getByRole("link", { name: "Budgets", exact: true }).click();
  await expect(page.getByLabel("Budget Fiscal Year filter")).toContainText("FY2027 — Draft");
  await page.getByRole("button", { name: "New budget" }).click();
  const b = page.getByRole("dialog");
  await expect(b.getByLabel("Create Budget Fiscal Year")).toContainText("FY2027 — Draft");
  await b.getByLabel("Budget code (e.g. 1000)").fill("1000");
  await b.getByLabel("Name").fill("Operations");
  await b.getByLabel("Amount").fill("100000");
  await b.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("row", { name: /1000 Operations/ })).toContainText("Draft (unapproved)");
  // sub-budget + Other recalculation
  await page.getByRole("button", { name: "+ Sub-budget" }).click();
  const c = page.getByRole("dialog");
  await c.getByLabel("Sub-budget code (e.g. 01)").fill("01");
  await c.getByLabel("Name").fill("Travel");
  await c.getByLabel("Amount").fill("25000");
  await c.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("row", { name: /1000-01 Travel/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /1000-00 Other/ })).toContainText("$75,000.00");
  // institution + account
  await page.getByRole("link", { name: "Bank Accounts" }).click();
  await page.getByRole("button", { name: "New bank account" }).click();
  const a = page.getByRole("dialog", { name: "New bank account" });
  await a.getByRole("button", { name: "+ New institution" }).click();
  const fi = page.getByRole("dialog", { name: "New entity" });
  await fi.getByLabel(/Organization Name/).fill("First National");
  await fi.getByRole("button", { name: "Save" }).click();
  await expect(fi).toHaveCount(0);
  await a.getByLabel("Account name").fill("Operating");
  await expect(a.getByRole("combobox", { name: /Financial Institution/ })).toContainText("First National");
  await a.getByLabel("Full account number").fill("123456789012");
  await a.getByLabel("Primary register account").check();
  await a.getByLabel("Opening balance", { exact: true }).fill("5000.00");
  await a.getByRole("button", { name: "Save" }).click();
  const row = page.getByRole("row", { name: /Operating/ });
  await expect(row).toContainText("******9012");
  await expect(row).not.toContainText("123456789012");
  await row.getByRole("button", { name: "Reveal" }).click();
  await expect(row).toContainText("123456789012");
});

test("AC-FY-VIS-006 / AC-REG-001 / AC-SEC-011: Register User allocates to Draft FY; payloads inert", async ({ page }) => {
  await login(page, "ru1");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Users" })).toHaveCount(0);
  await nav.getByRole("link", { name: "Entities" }).click();
  await page.getByRole("button", { name: "New entity" }).click();
  const e = page.getByRole("dialog");
  const payload = `<img src=x onerror="window.__xss=1">Vendor`;
  await e.getByLabel(/Organization Name/).fill(payload);
  await e.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("cell", { name: payload })).toBeVisible();
  await nav.getByRole("link", { name: "Register" }).click();
  await expect(page.getByLabel("Register bank account")).toContainText("Operating - ******9012");
  await page.getByRole("button", { name: "New transaction" }).click();
  const t = page.getByRole("dialog");
  await t.getByLabel("Transaction date").fill("2026-08-15");
  await t.getByRole("combobox", { name: "Payee (entity)" }).fill("Vendor");
  await page.getByRole("option", { name: /Vendor/ }).click();
  await expect(t.getByRole("combobox", { name: "Payee (entity)" })).toHaveValue(payload);
  await t.getByLabel("Allocation 1 Fiscal Year").selectOption({ label: "FY2027 — Draft" });
  await t.getByLabel("Allocation 1 Budget").selectOption({ label: "1000-01 Travel (remaining $25,000.00)" });
  await t.getByLabel("Allocation 1 Amount").fill("250.00");
  await t.getByRole("button", { name: "Save" }).click();
  const row = page.getByRole("row", { name: /2026-08-15/ });
  await expect(row).toContainText("$250.00");
  await expect(row).toContainText("$4,750.00");
  await row.getByRole("button", { name: /Details/ }).click();
  await expect(page.getByRole("cell", { name: "FY2027", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();
});

test("AC-AUTH-SELF-001/004: self-service password change", async ({ page }) => {
  await login(page, "ru1");
  await page.getByRole("link", { name: "My account" }).click();
  await page.getByLabel("Current password").fill(PW);
  await page.getByLabel("New password", { exact: true }).fill("Brand-New-Pass-99");
  await page.getByLabel("Confirm new password").fill("Brand-New-Pass-99");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByText("Password changed.")).toBeVisible();
  await logout(page);
  await page.getByLabel("Username").fill("ru1");
  await page.getByLabel("Password").fill(PW);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid username or password.")).toBeVisible();
  await login(page, "ru1", "Brand-New-Pass-99");
});

test("AC-FY-004 / AC-REG-015: UI confirmation flows (gap warning, void)", async ({ page }) => {
  await login(page, "bm1");
  await page.getByRole("link", { name: "Fiscal Years" }).click();
  await page.getByRole("button", { name: "New Fiscal Year" }).click();
  const dlg = page.getByRole("dialog", { name: "New Fiscal Year" });
  await dlg.getByLabel("Identifier").fill("2029");
  await dlg.getByLabel("Start date").fill("2028-07-01");
  await dlg.getByLabel("End date").fill("2029-06-30");
  await expect(dlg.getByRole("alert").first()).toContainText("WARNING");
  await dlg.getByRole("button", { name: "Create Fiscal Year" }).click();
  const conf = page.getByRole("dialog", { name: "Confirmation required" });
  await expect(conf).toContainText("Uncovered dates");
  await expect(conf.getByRole("button", { name: "Confirm and continue" })).toBeDisabled();
  await conf.getByLabel(/explicitly confirm/).check();
  await conf.getByRole("button", { name: "Confirm and continue" }).click();
  await expect(page.getByRole("heading", { name: /FY2029/ })).toBeVisible();
  await logout(page);
  await login(page, "ru1", "Brand-New-Pass-99");
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("row", { name: /2026-08-15/ }).getByRole("button", { name: /Details/ }).click();
  await page.getByRole("button", { name: "Void…" }).click();
  const v = page.getByRole("dialog", { name: /Void transaction/ });
  await v.getByLabel("Void reason (required)").fill("Entered twice");
  await expect(v.getByRole("button", { name: "Void transaction" })).toBeDisabled();
  await v.getByLabel("Type VOID to confirm").fill("VOID");
  await v.getByRole("button", { name: "Void transaction" }).click();
  const row = page.getByRole("row", { name: /Details for transaction 1/ });
  await expect(row).toContainText("VOID");
  await expect(row).toContainText("$5,000.00");
});

test("AC-UI-THEME-003: core screens render in light and dark (screenshots)", async ({ page }) => {
  await login(page, "bm1");
  for (const theme of ["dark", "light"]) {
    const cur = await page.locator("html").getAttribute("data-theme");
    if (cur !== theme) await page.getByRole("button", { name: /Switch to/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    for (const [path, name] of [["/", "dashboard"], ["/fiscal-years/1", "fy-detail"], ["/budgets", "budgets"], ["/register", "register"], ["/bank-accounts", "bank-accounts"], ["/entities", "entities"], ["/reports", "reports"]]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `e2e-screenshots/${theme}-${name}.png`, fullPage: true });
    }
  }
});

test("CR-001: correct the date of a zero-dollar VOID record in the UI", async ({ page }) => {
  await login(page, "ru1", "Brand-New-Pass-99");
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "Zero-dollar VOID record" }).click();
  const z = page.getByRole("dialog", { name: /Zero-dollar VOID/ });
  await z.getByLabel("Date").fill("2026-09-01");
  await z.getByLabel("Check #").fill("1001");
  await z.getByLabel("Void reason (required)").fill("Damaged check");
  await z.getByRole("button", { name: "Create VOID record" }).click();
  const row = page.getByRole("row", { name: /2026-09-01/ }).first();
  await row.getByRole("button", { name: /Details/ }).click();
  await page.getByRole("button", { name: "Correct date…" }).click();
  const d = page.getByRole("dialog", { name: /Correct date of VOID/ });
  await d.getByLabel("Transaction date").fill("2026-09-20");
  await d.getByLabel("Reason (optional)").fill("Forgot to set the date");
  await d.getByRole("button", { name: "Save date" }).click();
  await expect(d).toHaveCount(0);
  const fixed = page.getByRole("row", { name: /2026-09-20/ }).first();
  await expect(fixed).toContainText("VOID");
  await expect(fixed).toContainText("1001");
});


// ---------------------------------------------------------------- v1.2 enhancements
async function apiAs(page: Page) {
  const me = await (await page.request.get("/api/auth/me")).json();
  return (url: string, data: any) => page.request.post(url, { headers: { "X-CSRF-Token": me.csrf_token }, data });
}

test("CR-006 / CR-004: searchable entity picker and 'no attachment' checkbox with warning", async ({ page }) => {
  await login(page, "ru1", "Brand-New-Pass-99");
  const post = await apiAs(page);
  for (const n of ["Alpha Supplies", "Beta Services", "Gamma Bank Interest"]) {
    expect((await post("/api/entities", { entity_type: "ORGANIZATION", organization_name: n, confirmations: ["DUPLICATE_ENTITY"] })).status()).toBe(201);
  }
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "New transaction" }).click();
  const t = page.getByRole("dialog", { name: /New transaction/ });
  await t.getByLabel("Transaction date").fill("2026-10-31");
  const picker = t.getByRole("combobox", { name: "Payee (entity)" });
  await picker.fill("gam");
  const list = page.getByRole("listbox");
  await expect(list.getByRole("option", { name: /Gamma Bank Interest/ })).toBeVisible();
  await expect(list.getByRole("option", { name: /Alpha Supplies/ })).toHaveCount(0);
  await picker.press("ArrowDown");
  await picker.press("Enter");
  await expect(picker).toHaveValue("Gamma Bank Interest");
  await t.getByLabel("Allocation 1 Fiscal Year").selectOption({ label: "FY2027 — Draft" });
  await t.getByLabel("Allocation 1 Budget").selectOption({ label: "1000-01 Travel (remaining $25,000.00)" });
  await t.getByLabel("Allocation 1 Amount").fill("0.87");
  await t.getByLabel("No attachment will be provided").click(); // warning first; box ticks only after confirming
  await expect(t.getByLabel("No attachment will be provided")).not.toBeChecked();
  const warn = page.getByRole("dialog", { name: "No attachment?" });
  await expect(warn).toContainText("should have supporting documentation");
  await warn.getByRole("button", { name: "Mark as no attachment" }).click();
  await expect(t.getByLabel("No attachment will be provided")).toBeChecked();
  await t.getByLabel("Reason no attachment is available (optional)").fill("Monthly bank service fee - auto debit");
  await t.getByRole("button", { name: "Save" }).click();
  const row = page.getByRole("row", { name: /2026-10-31/ }).first();
  await expect(row).toContainText("No attachment");
  await expect(row).toContainText("Gamma Bank Interest");
});

test("CR-003: transfer between two register accounts from the register", async ({ page }) => {
  await login(page, "bm1");
  const bm = await apiAs(page);
  const fi = await (await page.request.get("/api/entities?financial_institution=true")).json();
  expect((await bm("/api/bank-accounts", { account_name: "Savings", financial_institution_entity_id: fi[0].id, account_type: "SAVINGS",
    account_number: "555566667777", opening_balance: "0.00", opening_balance_date: "2026-07-01" })).status()).toBe(201);
  await logout(page);
  await login(page, "ru1", "Brand-New-Pass-99");
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "Transfer…" }).click();
  const d = page.getByRole("dialog", { name: "Transfer between accounts" });
  await d.getByLabel("To account").selectOption({ label: "Savings - ******7777" });
  await d.getByLabel("Amount").fill("300.00");
  await d.getByLabel("Transaction date").fill("2026-11-01");
  await d.getByLabel("Clear date (blank = uncleared)").fill("2026-11-02");
  const ent = d.getByRole("combobox", { name: "Entity" });
  await ent.fill("beta");
  await page.getByRole("listbox").getByRole("option", { name: /Beta Services/ }).click();
  await expect(ent).toHaveValue("Beta Services");
  await expect(d).toContainText("Transfer to ******7777 for Beta Services");
  await d.getByRole("button", { name: "Record transfer" }).click();
  await expect(d).toHaveCount(0);
  const row = page.getByRole("row", { name: /2026-11-01/ }).first();
  await expect(row).toContainText("Transfer");
  await expect(row).toContainText("Transfer to ******7777 for Beta Services");
  await expect(row).toContainText("$300.00");
  await page.getByLabel("Register bank account").selectOption({ label: "Savings - ******7777" });
  const dep = page.getByRole("row", { name: /2026-11-01/ }).first();
  await expect(dep).toContainText("Transfer from ******9012 for Beta Services");
  await expect(dep).toContainText("$300.00");
});

test("CR-005: per-allocation 'no attachment' flag on a split transaction", async ({ page }) => {
  await login(page, "ru1", "Brand-New-Pass-99");
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "New transaction" }).click();
  const t = page.getByRole("dialog", { name: /New transaction/ });
  await t.getByLabel("Transaction date").fill("2026-11-05");
  await t.getByRole("button", { name: "Split transaction" }).click();
  for (const [i, amt] of [[1, "4.00"], [2, "6.00"]] as const) {
    await t.getByLabel(`Allocation ${i} Fiscal Year`).selectOption({ label: "FY2027 — Draft" });
    const sel = t.getByLabel(`Allocation ${i} Budget`);
    await sel.selectOption((await sel.locator("option", { hasText: "1000-01 Travel" }).getAttribute("value"))!);
    await t.getByLabel(`Allocation ${i} Amount`).fill(amt);
  }
  await t.getByLabel("Allocation 1 no attachment").click();
  const warn = page.getByRole("dialog", { name: "No attachment?" });
  await expect(warn).toContainText("allocation 1 only");
  await warn.getByRole("button", { name: "Mark as no attachment" }).click();
  await expect(t.getByLabel("Allocation 1 no attachment")).toBeChecked();
  await expect(t.getByLabel("Allocation 2 no attachment")).not.toBeChecked();
  await t.getByLabel("Allocation 1 reason (optional)").fill("Split postage - no receipt");
  await t.getByRole("button", { name: "Save" }).click();
  await expect(t).toHaveCount(0);
  const row = page.getByRole("row", { name: /2026-11-05/ }).first();
  await expect(row).toContainText("$10.00");
  // parent has neither an attachment nor the flag and allocation 2 is undocumented -> listed as missing (checked below)
});

test("CR-002 / CR-005: reports page, audit PDF and entity report; documentation review warnings", async ({ page }) => {
  await login(page, "bm1");
  await page.getByRole("link", { name: "Reports" }).click();
  const open = page.getByRole("link", { name: "Open printable PDF" });
  const href = await open.getAttribute("href");
  expect(href).toContain("/api/reports/audit?fiscal_year_id=");
  const pdf = await page.request.get(href!);
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()["content-type"]).toBe("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await page.getByRole("tab", { name: "Entity activity" }).click();
  await page.getByLabel("Entity report account").selectOption({ label: "Operating - ******9012" });
  await page.getByRole("button", { name: "Run report" }).click();
  await expect(page.getByRole("row", { name: /Gamma Bank Interest/ })).toContainText("$0.87");
  await expect(page.getByRole("row", { name: /Transfers between accounts/ })).toContainText("$300.00");
  await expect(page.getByRole("link", { name: "Download CSV" })).toBeVisible();
  await page.goto("/fiscal-years/1");
  const review = page.getByRole("heading", { name: /Documentation review/ }).locator("..");
  // v1.4 CR-017: a "no attachment" mark WITH a reason counts as documented and is not listed
  await expect(review).not.toContainText("Monthly bank service fee - auto debit");
  const splitRow = review.getByRole("row", { name: /2026-11-05/ });
  await expect(splitRow).toContainText("Missing attachment");
  await expect(splitRow).toContainText("1 of 2 allocations undocumented");
  await expect(page.getByText(/transaction\(s\) have no supporting attachments/)).toBeVisible();
});

// ---------------------------------------------------------------- v1.3 enhancements
const PDF = Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");

async function pickTravel(dlg: any, i = 1) {
  await dlg.getByLabel(`Allocation ${i} Fiscal Year`).selectOption({ label: "FY2027 — Draft" });
  const sel = dlg.getByLabel(`Allocation ${i} Budget`);
  await sel.selectOption((await sel.locator("option", { hasText: "1000-01 Travel" }).getAttribute("value"))!);
}

test("CR-011 / CR-010: double-click saves once, files attach in the form, check numbers are unique", async ({ page }) => {
  await login(page, "ru1", "Brand-New-Pass-99");
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "New transaction" }).click();
  const t = page.getByRole("dialog", { name: /New transaction/ });
  await t.getByLabel("Transaction date").fill("2026-11-10");
  await t.getByLabel("Check #").fill("7001");
  await pickTravel(t);
  await t.getByLabel("Allocation 1 Amount").fill("12.34");
  await t.getByLabel("Transaction attachments").setInputFiles({ name: "receipt-7001.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(t).toContainText("receipt-7001.pdf");
  await t.getByRole("button", { name: "Save" }).dblclick();
  await expect(t).toHaveCount(0);
  await expect(page.getByRole("row", { name: /2026-11-10/ })).toHaveCount(1);
  await expect(page.getByRole("row", { name: /2026-11-10/ })).toContainText("📎1");
  // the same check number cannot be used twice in the account
  await page.getByRole("button", { name: "New transaction" }).click();
  const t2 = page.getByRole("dialog", { name: /New transaction/ });
  await t2.getByLabel("Transaction date").fill("2026-11-11");
  await t2.getByLabel("Check #").fill("7001");
  await pickTravel(t2);
  await t2.getByLabel("Allocation 1 Amount").fill("5.00");
  await t2.getByRole("button", { name: "Save" }).click();
  await expect(t2.getByRole("alert")).toContainText("Check number 7001 is already used");
  await t2.getByRole("button", { name: "Cancel" }).click();
});

test("CR-012: missing checks are listed in the Fiscal Year reviews and can be resolved", async ({ page }) => {
  await login(page, "ru1", "Brand-New-Pass-99");
  const post = await apiAs(page);
  const opts = await (await page.request.get("/api/budgets/selectable?fiscal_year_id=1&transaction_type=WITHDRAWAL")).json();
  const travel = opts.find((o: any) => o.label === "1000-01 Travel").id;
  expect((await post("/api/transactions", { bank_account_id: 1, transaction_type: "WITHDRAWAL", transaction_date: "2026-11-12",
    check_number: "7003", allocations: [{ budget_id: travel, amount: "3.00" }] })).status()).toBe(201);
  await page.getByRole("link", { name: "Register" }).click();
  await page.getByRole("button", { name: "Fiscal Year reviews" }).click();
  const sec = page.locator(".missing-checks");
  const row = sec.getByRole("row", { name: /^7002/ });
  await expect(row).toContainText("#7001");
  await expect(row).toContainText("#7003");
  await row.getByRole("button", { name: "Enter transaction" }).click();
  const t = page.getByRole("dialog", { name: /New transaction/ });
  await expect(t.getByLabel("Check #")).toHaveValue("7002");
  await t.getByRole("button", { name: "Cancel" }).click();
  await row.getByRole("button", { name: "Confirm not missing…" }).click();
  const d = page.getByRole("dialog", { name: /Confirm check #7002 not missing/ });
  await d.getByLabel("Note (required)").fill("Torn out of the checkbook and destroyed");
  await d.getByRole("button", { name: "Confirm not missing" }).click();
  await expect(d).toHaveCount(0);
  await expect(sec.getByRole("row", { name: /^7002/ })).toHaveCount(0);
});

test("CR-007 / CR-008: Fiscal Year document types, approval rules and the Close report", async ({ page }) => {
  await login(page, "bm1");
  const post = await apiAs(page);
  const r = await post("/api/fiscal-years", { identifier: "2031", start_date: "2030-07-01", end_date: "2031-06-30", confirmations: ["FY_GAP"] });
  expect(r.status()).toBe(201);
  const fy = await r.json();
  await page.goto(`/fiscal-years/${fy.id}`);
  await page.getByRole("button", { name: "Approve…" }).click();
  let dlg = page.getByRole("dialog", { name: /Approve FY2031/ });
  await expect(dlg).toContainText("Attach the Approval document");
  await dlg.getByLabel("I understand approval cannot be reversed.").check();
  await expect(dlg.getByRole("button", { name: "Approve" })).toBeDisabled();
  await dlg.getByRole("button", { name: "Cancel" }).click();
  // "no approval document" needs a strong confirmation
  await page.getByLabel(/No approval document — this organization/).click();
  const mark = page.getByRole("dialog", { name: "No approval document?" });
  await expect(mark).toContainText("The budget approval should be documented.");
  await mark.getByLabel("Reason (optional)").fill("Approved verbally at the annual meeting");
  await mark.getByLabel(/I understand and confirm/).check();
  await mark.getByRole("button", { name: "Mark as no approval document" }).click();
  await expect(page.locator(".fy-docs")).toContainText("Approved verbally at the annual meeting");
  // uploading an approval document removes the mark
  await page.getByLabel(/Add approval document/).setInputFiles({ name: "board-minutes.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(page.locator(".fy-docs")).toContainText("board-minutes.pdf");
  await expect(page.getByLabel(/No approval document — this organization/)).toHaveCount(0);
  await page.getByRole("button", { name: "Approve…" }).click();
  dlg = page.getByRole("dialog", { name: /Approve FY2031/ });
  await dlg.getByLabel("I understand approval cannot be reversed.").check();
  await dlg.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("heading", { name: /FY2031/, level: 1 })).toContainText("Approved");
  // an "other" document can be re-labelled as the Audit Signoff
  await page.getByLabel(/Add other document/).setInputFiles({ name: "auditor-letter.pdf", mimeType: "application/pdf", buffer: PDF });
  await page.getByLabel("Document type of auditor-letter.pdf").selectOption("AUDIT_SIGNOFF");
  const signoff = page.locator(".fy-docs section.attachments", { has: page.getByRole("heading", { name: /Audit Signoff/ }) });
  await expect(signoff).toContainText("auditor-letter.pdf");
  const readiness = page.locator("section.card", { has: page.getByRole("heading", { name: "Closure readiness" }) });
  await expect(readiness).not.toContainText("An Audit Signoff document is required");
  await page.locator(".fy-docs").evaluate((el) => el.scrollIntoView({ block: "start" }));
  await page.screenshot({ path: "e2e-screenshots/light-fy-documents.png" });
  // Close report on the Reports page
  await page.getByRole("link", { name: "Reports" }).click();
  await page.getByRole("tab", { name: "Fiscal Year Close" }).click();
  await page.getByLabel("Close report Fiscal Year").selectOption({ label: "FY2031 — Approved" });
  const href = await page.getByRole("link", { name: "Open Close report PDF" }).getAttribute("href");
  expect(href).toContain(`/api/reports/fy-close?fiscal_year_id=${fy.id}`);
  const pdf = await page.request.get(href!);
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("CR-013 / CR-014 / CR-015: fixed navigation, collapsible menu and pinned register header", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await login(page, "ru1", "Brand-New-Pass-99");
  const post = await apiAs(page);
  const opts = await (await page.request.get("/api/budgets/selectable?fiscal_year_id=1&transaction_type=WITHDRAWAL")).json();
  const travel = opts.find((o: any) => o.label === "1000-01 Travel").id;
  for (let i = 0; i < 30; i++) {
    const res = await post("/api/transactions", { bank_account_id: 1, transaction_type: "WITHDRAWAL", transaction_date: "2026-12-01",
      allocations: [{ budget_id: travel, amount: `1.${String(i).padStart(2, "0")}`, description: `Scroll ${i}` }] });
    expect(res.status()).toBe(201);
  }
  await page.getByRole("link", { name: "Register" }).click();
  await expect(page.getByRole("row", { name: /Scroll 29/ })).toBeVisible();
  await page.locator("main.content").evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await page.waitForTimeout(200);
  // top bar and navigation did not move; register header and column headings are still on screen
  expect((await page.locator("header.topbar").boundingBox())!.y).toBe(0);
  expect((await page.getByRole("link", { name: "Dashboard" }).boundingBox())!.y).toBeLessThan(150);
  const h1 = (await page.getByRole("heading", { name: "Register", level: 1 }).boundingBox())!;
  expect(h1.y).toBeGreaterThan(40);
  expect(h1.y).toBeLessThan(140);
  await expect(page.getByRole("button", { name: "New transaction" })).toBeInViewport();
  await expect(page.getByText("Current balance")).toBeInViewport();
  await expect(page.getByLabel("Search")).toBeInViewport();
  await expect(page.locator("table.register thead th", { hasText: "Withdrawal" })).toBeInViewport();
  await expect(page.getByRole("row", { name: /Scroll 0\b/ })).not.toBeInViewport();
  await page.screenshot({ path: "e2e-screenshots/light-register-scrolled.png" });
  // collapsible navigation: icons only, current page still highlighted, remembered after reload
  await page.getByRole("button", { name: "Collapse navigation" }).click();
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect.poll(async () => (await nav.boundingBox())!.width).toBeLessThan(70);
  await expect(nav.locator(".nav-label").first()).toBeHidden();
  await expect(nav.getByRole("link", { name: "Register" })).toHaveAttribute("aria-current", "page");
  await page.reload();
  await expect(page.getByRole("button", { name: "Expand navigation" })).toBeVisible();
  expect((await page.locator("header.topbar").boundingBox())!.width).toBe(1280);
  await page.screenshot({ path: "e2e-screenshots/light-register-collapsed.png" });
  await page.getByRole("button", { name: "Expand navigation" }).click();
  await expect(nav.getByText("Register", { exact: true })).toBeVisible();
});

// ---------------------------------------------------------------- v1.4 enhancements
test("CR-022 / CR-021: version in My Account for every user; bank balance total on the dashboard", async ({ page }) => {
  await login(page, "bm1");
  const total = page.getByTestId("bank-total");
  await expect(total).toContainText("Total (all accounts)");
  await expect(total).toContainText("$");
  await page.screenshot({ path: "e2e-screenshots/light-dashboard-v14.png", fullPage: true });
  await page.getByRole("link", { name: "My account" }).click();
  const about = page.getByRole("region", { name: "About" });
  await expect(about.getByTestId("app-version")).toHaveText(/^\d+\.\d+\.\d+$/);
  await expect(about).toContainText(process.env.FM_BUNDLE ? "Build" : "Development build");
  await expect(about).not.toContainText("Bind address");
  await page.screenshot({ path: "e2e-screenshots/light-account-v14.png", fullPage: true });
  await logout(page);
  await login(page, "admin");
  await page.getByRole("link", { name: "System/About" }).click();
  await expect(page.getByText("Bind address")).toBeVisible();
});

// ---------------------------------------------------------------- v1.4.1
test("CR-016: audit report signature page — wording, saved wordings, signers", async ({ page }) => {
  await login(page, "bm1");
  const post = await apiAs(page);
  for (const n of ["Jane Trustee", "John Trustee"]) {
    expect((await post("/api/entities", { entity_type: "INDIVIDUAL", primary_contact: n, confirmations: ["DUPLICATE_ENTITY"] })).status()).toBe(201);
  }
  await page.getByRole("link", { name: "Reports" }).click();
  await page.getByLabel("Include audit review signature page").check();
  await expect(page.getByLabel("Selected wording")).toContainText("We, the undersigned");
  // new wording with an unknown variable is refused before opening the PDF
  await page.getByLabel("New wording…").check();
  await page.getByLabel("Signature page wording").fill("We, the Trustees of {ORG}, approve {YEAR}.");
  await expect(page.getByRole("alert")).toContainText("Unknown variable(s): {YEAR}");
  await page.getByLabel("Signature page wording").fill("We, the Trustees of {ORG}, approve the records for {FY}.");
  await page.getByRole("button", { name: "Save for future use" }).click();
  await expect(page.getByText("Wording saved for future use.")).toBeVisible();
  await expect(page.getByLabel("Selected wording")).toContainText("We, the Trustees of {ORG}");
  // signers
  await page.getByRole("combobox", { name: "Signer 1" }).fill("Jane");
  await page.getByRole("listbox").getByRole("option", { name: /Jane Trustee/ }).click();
  await page.getByLabel("Signer 1 title").fill("Trustee");
  await page.getByRole("button", { name: "+ Add signer" }).click();
  await page.getByRole("combobox", { name: "Signer 2" }).fill("John");
  await page.getByRole("listbox").getByRole("option", { name: /John Trustee/ }).click();
  const href = await page.getByRole("link", { name: "Open printable PDF" }).getAttribute("href");
  expect(href).toContain("signature_page=true");
  expect(href).toContain("signature_template_id=");
  expect(href!.match(/signer_id=/g)!.length).toBe(2);
  const pdf = await page.request.get(href!);
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await page.screenshot({ path: "e2e-screenshots/light-reports-signature.png", fullPage: true });
  // delete the saved wording again
  await page.getByRole("button", { name: "Delete saved wording 1" }).click();
  await expect(page.getByRole("button", { name: "Delete saved wording 1" })).toHaveCount(0);
  await expect(page.getByLabel("Default wording")).toBeChecked();
});

test("CR-020: dashboard charts — defaults, choose charts per user, data tables, light and dark", async ({ page }) => {
  await login(page, "bm1");
  const charts = page.getByRole("region", { name: "Charts" });
  await expect(charts.getByTestId("chart-income_pie")).toBeVisible();
  await expect(charts.getByTestId("chart-monthly")).toBeVisible();
  await expect(charts.getByTestId("chart-expense_vs_budget")).toBeVisible();
  await expect(charts.getByTestId("chart-balances")).toHaveCount(0);
  await expect(charts.getByTestId("chart-monthly").locator(".recharts-surface").first()).toBeVisible();
  await charts.getByTestId("chart-income_pie").screenshot({ path: "e2e-screenshots/light-chart-income-pie.png" });
  // choose charts: add bank balances + cumulative net, remove the income pie; saved for this user
  await charts.getByRole("button", { name: "Choose charts" }).click();
  await charts.getByRole("checkbox", { name: "Bank balances (month end)" }).check();
  await charts.getByRole("checkbox", { name: "Cumulative net (income − expenses)" }).check();
  await charts.getByRole("checkbox", { name: "Income by budget" }).uncheck();
  await charts.getByRole("button", { name: "Done" }).click();
  await expect(charts.getByTestId("chart-balances")).toBeVisible();
  await expect(charts.getByTestId("chart-income_pie")).toHaveCount(0);
  // data table fallback
  const monthly = charts.getByTestId("chart-monthly");
  await monthly.getByText("Show data table").click();
  await expect(monthly.getByRole("table")).toContainText("Expenses");
  await page.screenshot({ path: "e2e-screenshots/light-dashboard-charts.png", fullPage: true });
  await page.reload();
  await expect(page.getByRole("region", { name: "Charts" }).getByTestId("chart-cumulative_net")).toBeVisible();
  await expect(page.getByRole("region", { name: "Charts" }).getByTestId("chart-income_pie")).toHaveCount(0);
  await page.getByRole("button", { name: /Switch to dark mode/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: "e2e-screenshots/dark-dashboard-charts.png", fullPage: true });
  // restore defaults for later tests
  await page.getByRole("button", { name: /Switch to light mode/ }).click();
  await charts.getByRole("button", { name: "Choose charts" }).click();
  for (const n of ["Bank balances (month end)", "Cumulative net (income − expenses)"]) await charts.getByRole("checkbox", { name: n }).uncheck();
  await charts.getByRole("checkbox", { name: "Income by budget" }).check();
});
