"""v1.6.1 CR-034: fundraiser buckets, cash-float classifications, exclusions and fundraiser documents."""
import pytest

from fmpoc.models import FiscalYear

from conftest import PDF_BYTES


@pytest.fixture
def gala(env, base):
    """A fundraiser with: float withdrawal 200, supplies 300, a 1450 deposit (200 float + 1250 sales), a 75 donation."""
    assert env.admin.put("/api/system/modules", {"fundraisers": True}).status_code == 200
    acct = base["acct"]["id"]
    env.txn(acct, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "200.00", "description": "Cash float"}], date="2026-09-10")
    env.txn(acct, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "300.00", "description": "Food supplies"}], date="2026-09-11")
    env.txn(acct, "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "1450.00", "description": "Gala takings"},
                              {"budget_id": base["inc_leaf"], "amount": "75.00", "description": "Unrelated donation"}], date="2026-09-14")
    f = env.bm.post("/api/fundraisers", {"name": "Gala", "start_date": "2026-09-12",
                                         "budget_ids": [base["inc"]["id"], base["exp"]["id"]]}).json()
    line = {x["description"]: x["allocation_id"] for x in f["lines"]}
    return {"id": f["id"], "line": line, "base": base}


def put_line(c, g, desc, body):
    return c.put(f"/api/fundraisers/{g['id']}/lines/{g['line'][desc]}", body)


def test_cash_float_exclusion_and_totals(env, gala):
    f = env.bm.get(f"/api/fundraisers/{gala['id']}").json()
    assert f["totals"]["income"] == "1525.00" and f["totals"]["expense"] == "500.00"
    # Register Users may manage lines; Budget Users and Auditors may not
    for c in (env.bu, env.auditor, env.admin):
        assert put_line(c, gala, "Cash float", {"excluded": True, "exclusion_reason": "x"}).status_code == 403
    # float out: the whole 200 withdrawal is not an expense of the fundraiser
    r = put_line(env.ru, gala, "Cash float", {"classification": {"kind": "CASH_FLOAT_OUT", "amount": "200.00", "note": "cash box"}})
    assert r.status_code == 200, r.text
    # float returned: 200 of the 1450 deposit is not income
    f = put_line(env.ru, gala, "Gala takings", {"classification": {"kind": "CASH_FLOAT_RETURNED", "amount": "200.00"}}).json()
    # exclude the unrelated donation (reason required)
    assert put_line(env.bm, gala, "Unrelated donation", {"excluded": True}).status_code == 422
    f = put_line(env.bm, gala, "Unrelated donation", {"excluded": True, "exclusion_reason": "General donation, not the gala"}).json()
    t = f["totals"]
    assert (t["income"], t["expense"], t["net"]) == ("1250.00", "300.00", "950.00")
    assert t["cash_float_out"] == "200.00" and t["cash_float_returned"] == "200.00"
    assert t["excluded_income"] == "75.00" and t["excluded_lines"] == 1 and t["roi"] == "3.1667"
    lines = {x["description"]: x for x in f["lines"]}
    assert lines["Gala takings"]["counted"] == "1250.00" and lines["Gala takings"]["classification"]["label"] == "Cash float returned"
    assert lines["Unrelated donation"]["excluded"] and lines["Unrelated donation"]["counted"] == "0.00"
    assert [c["net"] for c in f["cumulative"]] == ["0.00", "-300.00", "950.00"]
    # the list shows the same figures
    row = env.bu.get(f"/api/fundraisers?fiscal_year_id={gala['base']['fy']['id']}").json()[0]
    assert (row["income"], row["expense"]) == ("1250.00", "300.00")
    # validation: wrong side, more than the line, not a line of the fundraiser
    assert put_line(env.ru, gala, "Food supplies", {"classification": {"kind": "CASH_FLOAT_RETURNED", "amount": "1.00"}}).status_code == 422
    assert put_line(env.ru, gala, "Food supplies", {"classification": {"kind": "CASH_FLOAT_OUT", "amount": "300.01"}}).status_code == 422
    assert env.ru.put(f"/api/fundraisers/{gala['id']}/lines/999999", {"excluded": False}).status_code == 404
    # include again
    f = put_line(env.ru, gala, "Unrelated donation", {"excluded": False}).json()
    assert f["totals"]["income"] == "1325.00" and f["totals"]["excluded_lines"] == 0
    acts = [e["action"] for e in env.auditor.get("/api/audit-events?action=FUNDRAISER_LINE_UPDATED").json()["items"]]
    assert len(acts) == 4


def test_buckets_split_by_amount_and_unassigned(env, gala):
    fid = gala["id"]
    assert env.bu.post(f"/api/fundraisers/{fid}/buckets", {"name": "Food"}).status_code == 403
    f = env.ru.post(f"/api/fundraisers/{fid}/buckets", {"name": "Food sales", "description": "Burgers"}).json()
    f = env.bm.post(f"/api/fundraisers/{fid}/buckets", {"name": "Raffle"}).json()
    assert env.bm.post(f"/api/fundraisers/{fid}/buckets", {"name": "food SALES"}).status_code == 422  # duplicate name
    b = {x["name"]: x["id"] for x in f["buckets"]["items"]}
    put_line(env.ru, gala, "Gala takings", {"classification": {"kind": "CASH_FLOAT_RETURNED", "amount": "200.00"},
                                            "buckets": [{"bucket_id": b["Food sales"], "amount": "800.00"},
                                                        {"bucket_id": b["Raffle"], "amount": "400.00"}]})
    f = put_line(env.ru, gala, "Food supplies", {"buckets": [{"bucket_id": b["Food sales"], "amount": "300.00"}]}).json()
    bk = {x["name"]: x for x in f["buckets"]["items"]}
    assert (bk["Food sales"]["income"], bk["Food sales"]["expense"], bk["Food sales"]["net"]) == ("800.00", "300.00", "500.00")
    assert (bk["Raffle"]["income"], bk["Raffle"]["net"]) == ("400.00", "400.00")
    # unassigned = counted amounts not in a bucket: income 50 (takings) + 75 (donation); expense 200 (float line)
    assert f["buckets"]["unassigned"] == {"income": "125.00", "expense": "200.00", "net": "-75.00"}
    takings = next(x for x in f["lines"] if x["description"] == "Gala takings")
    assert takings["unassigned"] == "50.00" and len(takings["buckets"]) == 2
    # more than the counted amount (1450 - 200 float) is refused; so is another fundraiser's bucket
    r = put_line(env.ru, gala, "Gala takings", {"classification": {"kind": "CASH_FLOAT_RETURNED", "amount": "200.00"},
                                                "buckets": [{"bucket_id": b["Food sales"], "amount": "1250.01"}]})
    assert r.status_code == 422
    other = env.bm.post("/api/fundraisers", {"name": "Other", "start_date": "2026-09-20", "budget_ids": []}).json()
    ob = env.bm.post(f"/api/fundraisers/{other['id']}/buckets", {"name": "X"}).json()["buckets"]["items"][0]["id"]
    assert put_line(env.ru, gala, "Food supplies", {"buckets": [{"bucket_id": ob, "amount": "1.00"}]}).status_code == 404
    # excluding a line clears its buckets; rename and delete a bucket (its lines become unassigned)
    assert put_line(env.ru, gala, "Food supplies", {"excluded": True, "exclusion_reason": "r", "buckets": [{"bucket_id": b["Raffle"], "amount": "1.00"}]}).status_code == 422
    f = put_line(env.ru, gala, "Food supplies", {"excluded": True, "exclusion_reason": "moved"}).json()
    assert next(x for x in f["buckets"]["items"] if x["name"] == "Food sales")["expense"] == "0.00"
    f = env.ru.put(f"/api/fundraisers/{fid}/buckets/{b['Raffle']}", {"name": "Prize raffle"}).json()
    assert "Prize raffle" in [x["name"] for x in f["buckets"]["items"]]
    f = env.ru.delete(f"/api/fundraisers/{fid}/buckets/{b['Food sales']}").json()
    assert [x["name"] for x in f["buckets"]["items"]] == ["Prize raffle"]
    assert f["buckets"]["unassigned"]["income"] == "925.00"  # 1250 + 75 - 400
    # a fundraiser with management data cannot be deleted, only archived
    r = env.bm.delete(f"/api/fundraisers/{fid}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "FUNDRAISER_IN_USE"


def test_fundraiser_documents(env, gala):
    fid = gala["id"]
    up = lambda c: c.c.post(f"/api/attachments?owner_type=fundraiser&owner_id={fid}",  # noqa: E731
                            files={"file": ("flyer.pdf", PDF_BYTES, "application/pdf")}, headers={"X-CSRF-Token": c.csrf})
    assert up(env.bu).status_code == 403 and up(env.auditor).status_code == 403
    att = up(env.ru)
    assert att.status_code == 201 and att.json()["fundraiser_id"] == fid
    docs = env.auditor.get(f"/api/attachments?owner_type=fundraiser&owner_id={fid}").json()
    assert [d["original_filename"] for d in docs] == ["flyer.pdf"]
    assert env.bu.get(docs[0]["content_url"]).status_code == 200
    assert env.bm.delete(f"/api/fundraisers/{fid}").status_code == 409  # has a document
    # module off: fundraiser documents are not reachable
    env.admin.put("/api/system/modules", {"fundraisers": False})
    assert env.bu.get(docs[0]["content_url"]).status_code == 404
    env.admin.put("/api/system/modules", {"fundraisers": True})
    assert env.bu.post(f"/api/attachments/{docs[0]['id']}/remove").status_code == 403
    assert env.bm.post(f"/api/attachments/{docs[0]['id']}/remove").status_code == 200
    assert env.bm.get(f"/api/attachments?owner_type=fundraiser&owner_id={fid}").json() == []


def test_closed_fiscal_year_freezes_lines_and_budget_removal_drops_adjustments(env, gala, app):
    fid, base = gala["id"], gala["base"]
    b = env.ru.post(f"/api/fundraisers/{fid}/buckets", {"name": "Food"}).json()["buckets"]["items"][0]["id"]
    put_line(env.ru, gala, "Food supplies", {"buckets": [{"bucket_id": b, "amount": "100.00"}]})
    put_line(env.ru, gala, "Cash float", {"classification": {"kind": "CASH_FLOAT_OUT", "amount": "200.00"}})
    # removing the expense budget drops the adjustments on its lines (audited)
    f = env.bm.put(f"/api/fundraisers/{fid}", {"name": "Gala", "start_date": "2026-09-12", "budget_ids": [base["inc"]["id"]]}).json()
    assert f["totals"]["expense"] == "0.00" and f["totals"]["cash_float_out"] == "0.00"
    f = env.bm.put(f"/api/fundraisers/{fid}", {"name": "Gala", "start_date": "2026-09-12",
                                               "budget_ids": [base["inc"]["id"], base["exp"]["id"]]}).json()
    assert f["totals"]["expense"] == "500.00" and f["buckets"]["items"][0]["expense"] == "0.00"
    ev = env.auditor.get("/api/audit-events?action=FUNDRAISER_UPDATED&sort=id&direction=asc").json()["items"]
    assert ev[0]["after"]["dropped_line_adjustments"] == 2
    # closed Fiscal Year: lines, buckets and documents are frozen
    put_line(env.ru, gala, "Food supplies", {"buckets": [{"bucket_id": b, "amount": "100.00"}]})
    with app.state.session_factory() as db:
        db.get(FiscalYear, base["fy"]["id"]).status = "CLOSED"
        db.commit()
    f = env.ru.get(f"/api/fundraisers/{fid}").json()
    assert f["read_only"] and all(x["read_only"] for x in f["lines"])
    r = put_line(env.ru, gala, "Food supplies", {"excluded": True, "exclusion_reason": "late"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "FISCAL_YEAR_CLOSED"
    assert env.ru.post(f"/api/fundraisers/{fid}/buckets", {"name": "New"}).status_code == 409
    assert env.ru.delete(f"/api/fundraisers/{fid}/buckets/{b}").status_code == 409
    r = env.ru.c.post(f"/api/attachments?owner_type=fundraiser&owner_id={fid}",
                      files={"file": ("a.pdf", PDF_BYTES, "application/pdf")}, headers={"X-CSRF-Token": env.ru.csrf})
    assert r.status_code == 409
