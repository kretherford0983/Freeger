"""v1.2 CR-003 account-to-account transfers."""


def transfer(env, src, dst, amount="250.00", expect=201, **kw):
    r = env.ru.post("/api/transfers", {"from_account_id": src, "to_account_id": dst, "amount": amount,
                                        "transaction_date": "2026-08-10", **kw})
    assert r.status_code == expect, r.text
    return r.json()


def bal(env, acct_id):
    return env.bu.get(f"/api/bank-accounts/{acct_id}").json()["current_balance"]


def test_cr003_transfer_creates_linked_legs_with_generated_descriptions(env, base):
    src = base["acct"]
    dst = env.account(number="55556666777", opening="0.00")
    r = transfer(env, src["id"], dst["id"], clear_date="2026-08-11", notes="Move reserve")
    w, d = r["withdrawal"], r["deposit"]
    assert w["transaction_type"] == "WITHDRAWAL" and w["bank_account_id"] == src["id"]
    assert d["transaction_type"] == "DEPOSIT" and d["bank_account_id"] == dst["id"]
    assert w["total"] == d["total"] == "250.00"
    assert w["transaction_date"] == d["transaction_date"] == "2026-08-10"
    assert w["clear_date"] == d["clear_date"] == "2026-08-11"
    assert w["allocations"][0]["description"] == f"Transfer to {dst['account_number_masked']} for Acme Org"
    assert d["allocations"][0]["description"] == f"Transfer from {src['account_number_masked']} for Acme Org"
    assert w["transfer"]["counterpart_transaction_id"] == d["id"] and d["transfer"]["direction"] == "IN"
    assert w["allocations"][0]["budget"]["is_budget_zero"] and d["allocations"][0]["budget"]["is_budget_zero"]
    assert w["no_attachment"] and w["notes"] == "Move reserve"
    # balances move exactly once, budgets are unaffected
    assert bal(env, src["id"]) == "750.00" and bal(env, dst["id"]) == "250.00"
    tree = env.bu.get(f"/api/budgets?fiscal_year_id={base['fy']['id']}").json()
    assert tree["expense"][0]["actual"] == "0.00" and tree["income"][0]["actual"] == "0.00"
    assert tree["budget_zero"]["inflow"] == "250.00" and tree["budget_zero"]["outflow"] == "250.00"
    # both legs audited
    ev = env.auditor.get("/api/audit-events?action=TRANSFER_CREATED").json()
    assert ev["total"] == 2


def test_cr003_void_voids_both_legs(env, base):
    dst = env.account(opening="0.00")
    r = transfer(env, base["acct"]["id"], dst["id"])
    v = env.ru.post(f"/api/transactions/{r['deposit']['id']}/void", {"reason": "Wrong amount", "confirm_irreversible": True})
    assert v.status_code == 200
    w = env.ru.get(f"/api/transactions/{r['withdrawal']['id']}").json()
    assert w["status"] == "VOID" and w["void_reason"] == "Wrong amount"
    assert bal(env, base["acct"]["id"]) == "1000.00" and bal(env, dst["id"]) == "0.00"


def test_cr003_leg_edit_restrictions(env, base):
    dst = env.account(opening="0.00")
    r = transfer(env, base["acct"]["id"], dst["id"])
    wid, did = r["withdrawal"]["id"], r["deposit"]["id"]
    # each bank may clear on its own date
    assert env.ru.patch(f"/api/transactions/{did}", {"clear_date": "2026-08-12"}).json()["clear_date"] == "2026-08-12"
    assert env.ru.get(f"/api/transactions/{wid}").json()["clear_date"] is None
    assert env.ru.patch(f"/api/transactions/{wid}", {"notes": "memo"}).status_code == 200
    aid = r["withdrawal"]["allocations"][0]["id"]
    for body in [{"transaction_date": "2026-08-20"}, {"entity_id": None},
                 {"allocations": [{"id": aid, "budget_id": base["exp_leaf"], "amount": "1.00"}]},
                 {"transaction_type": "DEPOSIT", "allocations": [], "confirmations": ["TYPE_CHANGE"]}]:
        rr = env.ru.patch(f"/api/transactions/{wid}", body)
        assert rr.status_code in (409, 422), body
    assert env.ru.get(f"/api/transactions/{wid}").json()["total"] == "250.00"


def test_cr003_validation_and_permissions(env, base):
    a = base["acct"]["id"]
    dst = env.account(opening="0.00")
    inv = env.account(atype="INVESTMENT")
    transfer(env, a, a, expect=422)
    transfer(env, a, dst["id"], amount="0", expect=422)
    transfer(env, a, dst["id"], amount="-5", expect=422)
    transfer(env, a, dst["id"], amount="1.001", expect=422)
    transfer(env, a, inv["id"], expect=422)  # not register-enabled
    transfer(env, a, 99999, expect=404)
    r = env.ru.post("/api/transfers", {"from_account_id": a, "to_account_id": dst["id"], "amount": "1",
                                        "description": "custom"})
    assert r.status_code == 422  # description is system generated; not writable
    for c in (env.bm, env.bu, env.auditor, env.admin):
        assert c.post("/api/transfers", {"from_account_id": a, "to_account_id": dst["id"], "amount": "1"}).status_code == 403
    assert env.ru.c.post("/api/transfers", json={"from_account_id": a, "to_account_id": dst["id"], "amount": "1"}).status_code == 403
    # a closed destination account is refused
    closed = env.account(opening="0.00")
    env.bm.post(f"/api/bank-accounts/{closed['id']}/close", {"reason": "done"})
    transfer(env, a, closed["id"], expect=409)
    assert env.bu.get(f"/api/register?bank_account_id={a}").json()["transactions"] == []


def test_cr003_fiscal_year_rules(env, base):
    dst = env.account(opening="0.00")
    # date outside every FY: uses the closest open FY's Budget 0 (non-budget activity, no review item)
    r = transfer(env, base["acct"]["id"], dst["id"], transaction_date="2028-01-15")
    assert r["withdrawal"]["allocations"][0]["reviews"] == []
    # overlapping open FYs: explicit Fiscal Year required
    env.fy("2027B", "2027-01-01", "2027-12-31", confirmations=["FY_OVERLAP"])
    rr = env.ru.post("/api/transfers", {"from_account_id": base["acct"]["id"], "to_account_id": dst["id"],
                                         "amount": "1", "transaction_date": "2027-03-01"})
    assert rr.status_code == 422 and rr.json()["error"]["code"] == "AMBIGUOUS_FISCAL_YEAR"
    ok = transfer(env, base["acct"]["id"], dst["id"], amount="1", transaction_date="2027-03-01",
                  fiscal_year_id=base["fy"]["id"])
    assert ok["deposit"]["allocations"][0]["budget"]["fiscal_year"]["id"] == base["fy"]["id"]


def test_cr003_transfer_listed_as_documentation_warning(env, base):
    dst = env.account(opening="0.00")
    r = transfer(env, base["acct"]["id"], dst["id"])
    items = env.bu.get(f"/api/fiscal-years/{base['fy']['id']}/documentation-review").json()["items"]
    cats = {i["transaction_id"]: (i["category"], i["is_transfer"]) for i in items}
    assert cats[r["withdrawal"]["id"]] == ("NO_ATTACHMENT_MARKED", True)


def test_cr003_transfer_entity_used_in_description(env, base):
    """v1.2.1: the selected Entity is recorded on both legs and named in the generated descriptions."""
    dst = env.account(opening="0.00")
    org = env.entity("Friends of the Library")
    r = transfer(env, base["acct"]["id"], dst["id"], entity_id=org["id"], amount="75.00")
    w, d = r["withdrawal"], r["deposit"]
    assert w["allocations"][0]["description"] == f"Transfer to {dst['account_number_masked']} for Friends of the Library"
    assert d["allocations"][0]["description"] == f"Transfer from {base['acct']['account_number_masked']} for Friends of the Library"
    assert w["entity"]["id"] == d["entity"]["id"] == org["id"]
    assert w["status"] == d["status"] == "ACTIVE"
    # inactive / hidden entities are refused
    env.ru.post(f"/api/entities/{org['id']}/inactivate", {})
    transfer(env, base["acct"]["id"], dst["id"], entity_id=org["id"], expect=422)
    transfer(env, base["acct"]["id"], dst["id"], entity_id=99999, expect=422)
