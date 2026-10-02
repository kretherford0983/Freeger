"""v1.3 CR-012: missing check review."""


def check(env, base, number, date="2026-08-01", account=None, **kw):
    b = {"bank_account_id": account or base["acct"]["id"], "transaction_type": "WITHDRAWAL", "transaction_date": date,
         "check_number": number, "allocations": [{"budget_id": base["exp_leaf"], "amount": "10.00"}],
         "confirmations": ["POSSIBLE_DUPLICATE"]}  # identical cheques on purpose; only the numbers matter here
    b.update(kw)
    r = env.ru.post("/api/transactions", b)
    assert r.status_code == 201, r.text
    return r.json()


def review(env, base, account=None):
    return env.bu.get(f"/api/check-review?bank_account_id={account or base['acct']['id']}").json()


def missing(env, base, account=None):
    return [(m["first_number"], m["last_number"]) for m in review(env, base, account)["missing"]]


def test_cr012_gaps_are_flagged_and_clear_themselves(env, base):
    for n in ("1", "2", "3", "6"):
        check(env, base, n)
    assert missing(env, base) == [(4, 4), (5, 5)]
    item = review(env, base)["missing"][0]
    assert item["before"]["check_number"] == "3" and item["after"]["check_number"] == "6"
    assert item["fiscal_year_ids"] == [base["fy"]["id"]]
    # entering check 4 resolves it; a zero-dollar VOID record documents check 5 (spoiled check)
    check(env, base, "4")
    env.ru.post("/api/transactions", {"bank_account_id": base["acct"]["id"], "transaction_type": "WITHDRAWAL",
                                      "transaction_date": "2026-08-02", "check_number": "5", "create_as_void": True,
                                      "void_reason": "Spoiled"})
    assert missing(env, base) == []


def test_cr012_rules_numeric_void_and_per_account(env, base):
    for n in ("101", "0104", "A-12", "106"):
        check(env, base, n)
    # sequence starts at the lowest recorded number; leading zeros ignored; non-numeric numbers ignored
    assert missing(env, base) == [(102, 102), (103, 103), (105, 105)]
    # a VOID transaction still documents its number
    t = check(env, base, "105")
    env.ru.post(f"/api/transactions/{t['id']}/void", {"reason": "Lost", "confirm_irreversible": True})
    assert missing(env, base) == [(102, 102), (103, 103)]
    # other accounts are independent
    other = env.account(opening="500.00")
    check(env, base, "7", account=other["id"])
    check(env, base, "9", account=other["id"])
    assert missing(env, base, other["id"]) == [(8, 8)]
    everything = env.bu.get("/api/check-review").json()["missing"]
    assert {(m["bank_account"]["id"], m["first_number"]) for m in everything} == {
        (base["acct"]["id"], 102), (base["acct"]["id"], 103), (other["id"], 8)}


def test_cr012_large_gap_is_one_range_and_can_be_confirmed(env, base):
    check(env, base, "150")
    check(env, base, "5001")
    items = review(env, base)["missing"]
    assert len(items) == 1 and items[0]["first_number"] == 151 and items[0]["count"] == 4850
    url = "/api/check-review/acknowledge"
    body = {"bank_account_id": base["acct"]["id"], "first_number": 151, "last_number": 5000,
            "note": "New checkbook started at 5001"}
    assert env.bu.post(url, body).status_code == 403
    assert env.ru.c.post(url, json=body).status_code == 403
    assert env.ru.post(url, {**body, "note": ""}).status_code == 422
    assert env.ru.post(url, {**body, "last_number": 5001}).status_code == 409  # 5001 is not missing
    assert env.ru.post(url, body).status_code == 201
    assert missing(env, base) == []
    ev = env.auditor.get("/api/audit-events?action=CHECK_NUMBERS_CONFIRMED_NOT_MISSING").json()["items"][0]
    assert ev["after"]["note"] == "New checkbook started at 5001"


def test_cr012_partial_confirmation_and_closure_warning(env, base):
    fy = base["fy"]["id"]
    for n in ("10", "14"):
        check(env, base, n, clear_date="2026-08-03")
    env.ru.post("/api/check-review/acknowledge", {"bank_account_id": base["acct"]["id"], "first_number": 12,
                                                  "last_number": 12, "note": "Destroyed"})
    assert missing(env, base) == [(11, 11), (13, 13)]
    chk = env.bm.get(f"/api/fiscal-years/{fy}/closure-check").json()
    w = {x["code"]: x for x in chk["warnings"]}
    assert "MISSING_CHECKS" in w and "2 check number(s)" in w["MISSING_CHECKS"]["message"]
    assert "MISSING_CHECKS" not in {b["code"] for b in chk["blockers"]}  # warning only (Q9)


def test_cr012_preexisting_duplicates_listed(env, base, app):
    a = check(env, base, "300")
    b = check(env, base, "301")
    from fmpoc.models import RegisterTransaction
    with app.state.session_factory() as db:  # data entered before v1.3 could repeat a number
        db.get(RegisterTransaction, b["id"]).check_number = "300"
        db.commit()
    dups = review(env, base)["duplicates"]
    assert len(dups) == 1 and dups[0]["check_number"] == 300
    assert {t["transaction_id"] for t in dups[0]["transactions"]} == {a["id"], b["id"]}
    # fixing one of them is allowed as long as the new number is free
    assert env.ru.patch(f"/api/transactions/{b['id']}", {"check_number": "301"}).status_code == 200
    assert review(env, base)["duplicates"] == []


def test_cr014_collapsed_navigation_preference_is_per_user(env):
    assert env.ru.get("/api/auth/me").json()["nav_collapsed"] is False
    r = env.ru.put("/api/me/preferences", {"nav_collapsed": True})
    assert r.status_code == 200 and r.json()["nav_collapsed"] is True and r.json()["theme"] == "light"
    assert env.ru.get("/api/auth/me").json()["nav_collapsed"] is True
    assert env.bu.get("/api/auth/me").json()["nav_collapsed"] is False  # other users unaffected
    assert env.ru.put("/api/me/preferences", {"nav_collapsed": "maybe"}).status_code == 422
    assert env.ru.c.put("/api/me/preferences", json={"nav_collapsed": False}).status_code == 403  # CSRF
