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
  await expect(d).toContainText("Transfer to ******7777");
  await d.getByRole("button", { name: "Record transfer" }).click();
  await expect(d).toHaveCount(0);
  const row = page.getByRole("row", { name: /2026-11-01/ }).first();
  await expect(row).toContainText("Transfer");
  await expect(row).toContainText("Transfer to ******7777 for E2E Org");
  await expect(row).toContainText("$300.00");
  await page.getByLabel("Register bank account").selectOption({ label: "Savings - ******7777" });
  const dep = page.getByRole("row", { name: /2026-11-01/ }).first();
  await expect(dep).toContainText("Transfer from ******9012 for E2E Org");
  await expect(dep).toContainText("$300.00");
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
  await expect(review).toContainText("No attachment");
  await expect(review).toContainText("Monthly bank service fee - auto debit");
  await expect(page.getByText(/transaction\(s\) are marked 'no attachment will be provided'/)).toBeVisible();
});
