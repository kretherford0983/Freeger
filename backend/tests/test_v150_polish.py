"""v1.5.0 CR-028 (bank account groups) and CR-029 (signature page preview)."""
import io

from pypdf import PdfReader


def test_cr028_groups_on_accounts_and_dashboard(env, base):
    sav = env.account(opening="200.00", atype="SAVINGS")
    mm = env.account(opening="300.00", atype="MONEY_MARKET")
    inv = env.account(opening="400.00", atype="INVESTMENT", register_enabled=False, current_balance="400.00")
    cash = env.account(opening="5.00", atype="CASH", register_enabled=False, current_balance="5.00")
    accts = {a["id"]: a for a in env.bu.get("/api/bank-accounts").json()}
    assert accts[base["acct"]["id"]]["group"] == "CHECKING_SAVINGS" and accts[sav["id"]]["group"] == "CHECKING_SAVINGS"
    assert {accts[x["id"]]["group"] for x in (mm, inv, cash)} == {"INVESTMENTS_OTHER"}
    d = env.bu.get("/api/dashboard").json()
    g = {x["key"]: x for x in d["bank_account_groups"]}
    assert [x["key"] for x in d["bank_account_groups"]] == ["CHECKING_SAVINGS", "INVESTMENTS_OTHER"]
    assert g["CHECKING_SAVINGS"]["label"] == "Checking & Savings" and g["INVESTMENTS_OTHER"]["label"] == "Investments and Other"
    assert set(g["CHECKING_SAVINGS"]["account_ids"]) == {base["acct"]["id"], sav["id"]}
    assert g["CHECKING_SAVINGS"]["total"] == "1200.00"
    assert g["INVESTMENTS_OTHER"]["total"] == "705.00"
    assert d["bank_accounts_total"] == "1905.00"


def _text(pdf: bytes) -> tuple[int, str]:
    r = PdfReader(io.BytesIO(pdf))
    return len(r.pages), " ".join(" ".join((p.extract_text() or "") for p in r.pages).split())


def test_cr029_signature_page_preview(env, base):
    fy = base["fy"]["id"]
    p = env.entity("Pat Signer", etype="INDIVIDUAL")
    r = env.auditor.get(f"/api/reports/audit/signature-page?fiscal_year_id={fy}&signer_id={p['id']}&signer_title=Trustee")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers["content-disposition"] and "audit-signature-page" in r.headers["content-disposition"]
    pages, text = _text(r.content)
    assert pages == 1 and "We, the undersigned" in text and "Pat Signer, Trustee" in text and "Acme Org" in text
    r = env.bm.get(f"/api/reports/audit/signature-page?fiscal_year_id={fy}&signature_text=Only+%7BORG%7D+%7BFYE%7D")
    assert "Only Acme Org June 30, 2027" in _text(r.content)[1]
    assert env.bm.get(f"/api/reports/audit/signature-page?fiscal_year_id={fy}&signature_text=%7BBAD%7D").status_code == 422
    assert env.admin.get(f"/api/reports/audit/signature-page?fiscal_year_id={fy}").status_code == 403
    ev = env.auditor.get("/api/audit-events?action=REPORT_GENERATED").json()["items"]
    assert any(e["after"].get("report") == "SIGNATURE_PAGE" for e in ev)
