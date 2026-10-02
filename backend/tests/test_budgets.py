"""Budgets. AC-BUD-001..011."""


def _tree(env, fy_id, client=None):
    return (client or env.bm).get(f"/api/budgets?fiscal_year_id={fy_id}").json()


def test_ac_bud_001_automatic_other(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100000.00")
    row = _tree(env, fy["id"])["expense"][0]
    assert row["simple"] is True and row["children"] == [] and row["other_amount"] == "100000.00"
    # stored system-managed Other exists and is used as the leaf behind the parent
    opts = env.selectable(fy["id"], "WITHDRAWAL")
    assert opts[0]["label"] == "1000 Operations" and opts[0]["id"] != p["id"]
    other = env.bm.get(f"/api/budgets/{opts[0]['id']}").json()
    assert other["is_other"] and other["system_managed"] and other["amount"] == "100000.00"


def test_ac_bud_002_child_and_other_recalc(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100000.00")
    env.budget(fy["id"], "01", "Travel", amount="25000.00", parent=p["id"])
    row = _tree(env, fy["id"])["expense"][0]
    assert row["simple"] is False and row["other_amount"] == "75000.00"
    labels = [c["label"] for c in row["children"]]
    assert labels == ["1000-01 Travel", "1000-00 Other"]


def test_ac_bud_003_children_cannot_exceed_parent(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100.00")
    c = env.budget(fy["id"], "01", "Travel", amount="60.00", parent=p["id"])
    r = env.bm.post("/api/budgets", {"fiscal_year_id": fy["id"], "parent_budget_id": p["id"], "code": "02",
                                     "name": "Meals", "amount": "50.00"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CHILDREN_EXCEED_PARENT"
    assert env.bm.patch(f"/api/budgets/{c['id']}", {"amount": "100.01"}).status_code == 422
    assert env.bm.patch(f"/api/budgets/{p['id']}", {"amount": "59.99"}).status_code == 422
    row = _tree(env, fy["id"])["expense"][0]
    assert len(row["children"]) == 2 and row["other_amount"] == "40.00"  # nothing persisted from rejected attempts


def test_ac_bud_004_005_zero_other_hidden_then_reappears(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100.00")
    c = env.budget(fy["id"], "01", "Travel", amount="100.00", parent=p["id"])
    row = _tree(env, fy["id"])["expense"][0]
    assert [x["label"] for x in row["children"]] == ["1000-01 Travel"]
    assert [o["label"] for o in env.selectable(fy["id"], "WITHDRAWAL") if not o["is_budget_zero"]] == ["1000-01 Travel"]
    # still stored
    hidden = _tree(env, fy["id"])["expense"][0]["other_amount"]
    assert hidden == "0.00"
    env.bm.patch(f"/api/budgets/{c['id']}", {"amount": "70.00"})
    row = _tree(env, fy["id"])["expense"][0]
    assert [x["label"] for x in row["children"]] == ["1000-01 Travel", "1000-00 Other"]
    assert "1000-00 Other" in [o["label"] for o in env.selectable(fy["id"], "WITHDRAWAL")]


def test_ac_bud_004_zero_other_rejected_for_new_allocation(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100.00")
    env.budget(fy["id"], "01", "Travel", amount="100.00", parent=p["id"])
    acct = env.account()
    from fmpoc.models import Budget
    with env.app.state.session_factory() as db:
        other_id = db.query(Budget).filter_by(parent_budget_id=p["id"], is_other=True).one().id
    r = env.ru.post("/api/transactions", {"bank_account_id": acct["id"], "transaction_type": "WITHDRAWAL",
                                          "transaction_date": "2026-08-01",
                                          "allocations": [{"budget_id": other_id, "amount": "1.00"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "OTHER_NOT_SELECTABLE"


def test_ac_bud_006_rollup_parent_not_selectable(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100.00")
    env.budget(fy["id"], "01", "Travel", amount="10.00", parent=p["id"])
    acct = env.account()
    assert p["id"] not in [o["id"] for o in env.selectable(fy["id"], "WITHDRAWAL")]
    r = env.ru.post("/api/transactions", {"bank_account_id": acct["id"], "transaction_type": "WITHDRAWAL",
                                          "transaction_date": "2026-08-01",
                                          "allocations": [{"budget_id": p["id"], "amount": "1.00"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "ROLLUP_NOT_SELECTABLE"


def test_ac_bud_007_display_identifier(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations")
    env.budget(fy["id"], "01", "Travel", amount="10.00", parent=p["id"])
    acct = env.account()
    opt = [o for o in env.selectable(fy["id"], "WITHDRAWAL") if o["label"] == "1000-01 Travel"][0]
    t = env.txn(acct["id"], "WITHDRAWAL", [{"budget_id": opt["id"], "amount": "1.00"}])
    assert t["allocations"][0]["budget"]["label"] == "1000-01 Travel"


def test_ac_bud_008_overage_allowed_negative_remaining(env, base):
    fy = base["fy"]["id"]
    small = env.budget(fy, "2000", "Small", "EXPENSE", "50.00")
    leaf = [o for o in env.selectable(fy, "WITHDRAWAL") if o["label"] == "2000 Small"][0]["id"]
    env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": leaf, "amount": "80.00"}])
    row = [r for r in _tree(env, fy)["expense"] if r["id"] == small["id"]][0]
    assert row["actual"] == "80.00" and row["remaining"] == "-30.00" and row["over_budget"] is True
    # still accepts more
    env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": leaf, "amount": "5.00"}])


def test_ac_bud_009_unlock_requires_reason_and_audits(env, base):
    fy = base["fy"]["id"]
    env.approve(fy)
    bid = base["exp"]["id"]
    assert env.bm.post(f"/api/budgets/{bid}/unlock", {"reason": ""}).status_code == 422
    assert env.bm.post(f"/api/budgets/{bid}/unlock", {"reason": "   "}).status_code == 422
    assert env.bm.post(f"/api/budgets/{bid}/unlock", {}).status_code == 422
    assert env.ru.post(f"/api/budgets/{bid}/unlock", {"reason": "x"}).status_code == 403
    r = env.bm.post(f"/api/budgets/{bid}/unlock", {"reason": "Board amendment #4"})
    assert r.status_code == 200 and r.json()["state"]["code"] == "APPROVED_UNLOCKED"
    ev = env.auditor.get(f"/api/audit-events?action=BUDGET_UNLOCKED&object_id={bid}").json()["items"]
    assert ev and ev[0]["after"]["reason"] == "Board amendment #4"
    # amendment possible while unlocked, then lock
    assert env.bm.patch(f"/api/budgets/{bid}", {"amount": "120000.00"}).status_code == 200
    assert env.bm.post(f"/api/budgets/{bid}/lock").json()["state"]["code"] == "APPROVED_LOCKED"


def test_ac_bud_010_rejected_budget(env, base):
    fy = base["fy"]["id"]
    b = env.budget(fy, "2000", "Proposed", "EXPENSE", "500.00")
    leaf = [o for o in env.selectable(fy, "WITHDRAWAL") if o["label"] == "2000 Proposed"][0]["id"]
    t = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": leaf, "amount": "20.00"}])
    r = env.bm.post(f"/api/budgets/{b['id']}/reject", {"reason": "Denied by board"})
    assert r.status_code == 200
    row = [x for x in _tree(env, fy)["expense"] if x["id"] == b["id"]][0]
    assert row["amount"] == "0.00" and row["requested_amount"] == "500.00" and row["actual"] == "20.00"
    assert row["state"] == {"code": "REJECTED", "icon": "X", "label": "Rejected", "tone": "red"}
    # history preserved
    assert env.ru.get(f"/api/transactions/{t['id']}").json()["allocations"][0]["budget"]["status"] == "REJECTED"
    # no new normal allocations
    assert leaf not in [o["id"] for o in env.selectable(fy, "WITHDRAWAL")]
    r = env.ru.post("/api/transactions", {"bank_account_id": base["acct"]["id"], "transaction_type": "WITHDRAWAL",
                                          "transaction_date": "2026-08-01", "allocations": [{"budget_id": leaf, "amount": "1"}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "BUDGET_NOT_ACTIVE"
    # existing allocation on rejected budget may remain when editing other fields
    assert env.ru.patch(f"/api/transactions/{t['id']}", {"notes": "memo"}).status_code == 200


def test_ac_bud_011_status_indicators(env, base):
    fy = base["fy"]["id"]
    rej = env.budget(fy, "3000", "R", "EXPENSE", "1.00")
    env.bm.post(f"/api/budgets/{rej['id']}/reject", {"reason": "no"})
    states = {r["display_code"]: r["state"] for r in _tree(env, fy)["expense"]}
    assert states["1000"] == {"code": "DRAFT", "icon": "?", "label": "Draft (unapproved)", "tone": "yellow"}
    assert states["3000"]["icon"] == "X" and states["3000"]["label"] == "Rejected"
    env.approve(fy)
    states = {r["display_code"]: r["state"] for r in _tree(env, fy)["expense"]}
    assert states["1000"]["icon"] == "lock-closed" and states["1000"]["tone"] == "green"
    env.bm.post(f"/api/budgets/{base['exp']['id']}/unlock", {"reason": "x"})
    states = {r["display_code"]: r["state"] for r in _tree(env, fy)["expense"]}
    assert states["1000"]["icon"] == "lock-open" and states["1000"]["label"] == "Approved and unlocked"


def test_other_is_not_user_editable_and_budget_zero_protected(env, base):
    fy = base["fy"]["id"]
    assert env.bm.patch(f"/api/budgets/{base['exp_leaf']}", {"amount": "5.00"}).status_code == 422
    b0 = _tree(env, fy)["budget_zero"]
    assert b0["is_budget_zero"]
    assert env.bm.patch(f"/api/budgets/{b0['id']}", {"name": "hack"}).status_code == 422
    assert env.bm.post(f"/api/budgets/{b0['id']}/reject", {"reason": "x"}).status_code == 422
    assert env.bm.post("/api/budgets", {"fiscal_year_id": fy, "code": "0", "name": "n", "budget_type": "EXPENSE",
                                        "amount": "1"}).status_code == 422
    assert env.bm.post("/api/budgets", {"fiscal_year_id": fy, "parent_budget_id": base["exp"]["id"], "code": "00",
                                        "name": "n", "amount": "1"}).status_code == 422


def test_budget_hierarchy_audited(env):
    fy = env.fy()
    p = env.budget(fy["id"], "1000", "Operations", "EXPENSE", "100.00")
    c = env.budget(fy["id"], "01", "Travel", amount="25.00", parent=p["id"])
    ev = env.auditor.get(f"/api/audit-events?object_type=budget&object_id={c['id']}").json()["items"]
    assert ev[0]["before"] is None and ev[0]["after"]["other_after"]["amount"] == "75.00"


def test_budget_validation(env):
    fy = env.fy()
    for body in [{"code": "1000", "name": "x", "budget_type": "EXPENSE", "amount": "1.001"},
                 {"code": "1000", "name": "x", "budget_type": "EXPENSE", "amount": "-5"},
                 {"code": "1000", "name": "x", "budget_type": "ASSET", "amount": "5"},
                 {"code": "10 00", "name": "x", "budget_type": "EXPENSE", "amount": "5"},
                 {"code": "1000", "name": "", "budget_type": "EXPENSE", "amount": "5"},
                 {"code": "1000", "name": "x", "budget_type": "EXPENSE", "amount": "abc"},
                 {"code": "1000", "name": "x", "budget_type": "EXPENSE", "amount": "NaN"},
                 {"code": "1000", "name": "x", "budget_type": "EXPENSE", "amount": "1e30"}]:
        assert env.bm.post("/api/budgets", {"fiscal_year_id": fy["id"], **body}).status_code == 422, body
