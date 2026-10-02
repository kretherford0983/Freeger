"""v1.6.4 CR-037 (cancelled fundraisers) and CR-038 (printable cash count sheet)."""
import io

from pypdf import PdfReader


def _text(pdf: bytes) -> tuple[int, str]:
    r = PdfReader(io.BytesIO(pdf))
    return len(r.pages), " ".join(" ".join((p.extract_text() or "") for p in r.pages).split())


def _fundraiser(env, base):
    assert env.admin.put("/api/system/modules", {"fundraisers": True}).status_code == 200
    env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "150.00", "description": "Deposit for hall"}], date="2026-09-01")
    return env.bm.post("/api/fundraisers", {"name": "Autumn Fair", "start_date": "2026-09-20",
                                            "budget_ids": [base["inc"]["id"], base["exp"]["id"]]}).json()["id"]


def test_cancel_and_reinstate(env, base):
    fid = _fundraiser(env, base)
    for c in (env.ru, env.bu, env.auditor):
        assert c.post(f"/api/fundraisers/{fid}/cancel", {"reason": "x"}).status_code == 403
    assert env.bm.post(f"/api/fundraisers/{fid}/cancel", {"reason": "  "}).status_code == 422
    f = env.bm.post(f"/api/fundraisers/{fid}/cancel", {"reason": "Venue flooded"}).json()
    assert f["status"] == "CANCELLED" and f["cancelled"] and f["cancel_reason"] == "Venue flooded"
    assert f["totals"]["expense"] == "150.00" and len(f["lines"]) == 1  # transactions still listed and counted
    assert env.bm.post(f"/api/fundraisers/{fid}/cancel", {"reason": "again"}).status_code == 409
    row = env.bu.get(f"/api/fundraisers?fiscal_year_id={base['fy']['id']}").json()[0]
    assert row["status"] == "CANCELLED" and row["cancel_reason"] == "Venue flooded"
    # still manageable; shown in the fundraiser report and in the Audit report
    assert env.ru.post(f"/api/fundraisers/{fid}/buckets", {"name": "Hall"}).status_code == 201
    text = _text(env.auditor.get(f"/api/fundraisers/{fid}/report").content)[1]
    assert "CANCELLED" in text and "did not take place as planned" in text and "Venue flooded" in text
    text = _text(env.auditor.get(f"/api/reports/audit?fiscal_year_id={base['fy']['id']}&include_fundraisers=true").content)[1]
    assert "did not take place as planned" in text and "Venue flooded" in text
    # archived wins in the status, the cancellation stays recorded
    assert env.bm.post(f"/api/fundraisers/{fid}/archive").json()["status"] == "ARCHIVED"
    env.bm.post(f"/api/fundraisers/{fid}/restore")
    f = env.bm.post(f"/api/fundraisers/{fid}/reinstate").json()
    assert f["status"] != "CANCELLED" and f["cancel_reason"] is None
    assert env.bm.post(f"/api/fundraisers/{fid}/reinstate").status_code == 409
    acts = [e["action"] for e in env.auditor.get("/api/audit-events?object_type=fundraiser&sort=id&direction=asc").json()["items"]]
    assert "FUNDRAISER_CANCELLED" in acts and "FUNDRAISER_REINSTATED" in acts


def test_cash_count_sheet(env, base):
    fid = _fundraiser(env, base)
    assert env.admin.get(f"/api/fundraisers/{fid}/count-sheet").status_code == 403
    r = env.bu.get(f"/api/fundraisers/{fid}/count-sheet")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "fundraiser-Autumn-Fair-cash-count-sheet.pdf" in r.headers["content-disposition"]
    pages, text = _text(r.content)
    assert pages == 1
    for want in ("Cash count sheet", "Acme Org", "Autumn Fair", "2026-09-20", "Date of count", "Time", "$100", "$2", "25¢",
                 "Check no.", "Cash total", "Check total", "Total counted", "Notes", "agree with the amounts"):
        assert want in text, want
    assert "Location" not in text and text.count("Name and title") == 3
    # chosen signers (up to five individuals, optional titles) - still one page
    people = [env.entity(f"Person {i}", etype="INDIVIDUAL")["id"] for i in range(5)]
    q = "&".join(f"signer_id={p}" for p in people) + "&signer_title=Treasurer"
    pages, text = _text(env.ru.get(f"/api/fundraisers/{fid}/count-sheet?{q}").content)
    assert pages == 1 and "Person 0, Treasurer" in text and "Person 4" in text and "Name and title" not in text
    org = env.entity("Some Company")["id"]
    assert env.ru.get(f"/api/fundraisers/{fid}/count-sheet?signer_id={org}").status_code == 422
    assert env.ru.get(f"/api/fundraisers/{fid}/count-sheet?signer_id={people[0]}&signer_id={people[0]}").status_code == 422
    ev = env.auditor.get("/api/audit-events?action=REPORT_GENERATED&object_type=fundraiser").json()["items"]
    assert any(e["after"]["report"] == "CASH_COUNT_SHEET" for e in ev)
