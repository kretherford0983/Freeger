"""CR-001 (change request after v1.1): the Transaction Date of a VOID transaction can be corrected.
Guards: only VOID transactions, only the date, Register User permission, CSRF, closed-FY protection, audit."""
from conftest import Api


def _zero_void(env, base, date="2026-08-01"):
    r = env.ru.post("/api/transactions", {"bank_account_id": base["acct"]["id"], "transaction_type": "WITHDRAWAL",
                                          "transaction_date": date, "check_number": "1001", "create_as_void": True,
                                          "void_reason": "Damaged check"})
    assert r.status_code == 201, r.text
    return r.json()


def test_cr001_zero_dollar_void_date_corrected_and_audited(env, base):
    t = _zero_void(env, base)
    r = env.ru.post(f"/api/transactions/{t['id']}/void-date", {"transaction_date": "2026-09-15",
                                                               "reason": "Entered with default date"})
    assert r.status_code == 200, r.text
    t2 = r.json()
    assert t2["transaction_date"] == "2026-09-15" and t2["status"] == "VOID" and t2["total"] == "0.00"
    assert t2["void_reason"] == "Damaged check" and t2["check_number"] == "1001"
    assert t2["entry_timestamp"] == t["entry_timestamp"] and t2["zero_dollar_void"] is True
    assert env.bu.get(f"/api/bank-accounts/{base['acct']['id']}").json()["current_balance"] == "1000.00"
    ev = env.auditor.get(f"/api/audit-events?action=TRANSACTION_VOID_DATE_CORRECTED&object_id={t['id']}").json()["items"]
    assert ev[0]["before"]["transaction_date"] == "2026-08-01" and ev[0]["after"]["transaction_date"] == "2026-09-15"
    assert ev[0]["after"]["reason"] == "Entered with default date" and ev[0]["actor_username"] == "reguser"


def test_cr001_zero_dollar_void_budget0_follows_new_fiscal_year(env, base):
    nxt = env.fy("2028", "2027-07-01", "2028-06-30")
    t = _zero_void(env, base)
    assert t["allocations"][0]["budget"]["fiscal_year"]["id"] == base["fy"]["id"]
    t2 = env.ru.post(f"/api/transactions/{t['id']}/void-date", {"transaction_date": "2027-08-10"}).json()
    b = t2["allocations"][0]["budget"]
    assert b["is_budget_zero"] and b["fiscal_year"]["id"] == nxt["id"]
    assert len(t2["allocations"]) == 1 and t2["allocations"][0]["amount"] == "0.00"


def test_cr001_regular_void_date_only(env, base):
    t = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "25.00"}])
    env.ru.post(f"/api/transactions/{t['id']}/void", {"reason": "dup", "confirm_irreversible": True})
    r = env.ru.post(f"/api/transactions/{t['id']}/void-date", {"transaction_date": "2026-08-20"})
    assert r.status_code == 200
    t2 = r.json()
    assert t2["transaction_date"] == "2026-08-20" and t2["status"] == "VOID" and t2["total"] == "25.00"
    assert t2["allocations"][0]["budget"]["id"] == t["allocations"][0]["budget"]["id"]
    assert env.bu.get(f"/api/budgets?fiscal_year_id={base['fy']['id']}").json()["expense"][0]["actual"] == "0.00"
    assert env.ru.post(f"/api/transactions/{t['id']}/void-date",
                       {"transaction_date": "2026-08-21", "fiscal_year_id": base["fy"]["id"]}).status_code == 422


def test_cr001_guards(env, base):
    active = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "5.00"}])
    assert env.ru.post(f"/api/transactions/{active['id']}/void-date", {"transaction_date": "2026-09-01"}).status_code == 409
    t = _zero_void(env, base)
    url = f"/api/transactions/{t['id']}/void-date"
    # unchanged date, bad input, protected fields, other roles, CSRF
    assert env.ru.post(url, {"transaction_date": "2026-08-01"}).status_code == 409
    assert env.ru.post(url, {"transaction_date": "not-a-date"}).status_code == 422
    assert env.ru.post(url, {}).status_code == 422
    for extra in [{"status": "ACTIVE"}, {"void_reason": "x"}, {"amount": "5"}, {"bank_account_id": 1}, {"check_number": "9"}]:
        assert env.ru.post(url, {"transaction_date": "2026-09-01", **extra}).status_code == 422, extra
    for c in (env.bm, env.bu, env.auditor, env.admin):
        assert c.post(url, {"transaction_date": "2026-09-01"}).status_code == 403
    assert env.ru.c.post(url, json={"transaction_date": "2026-09-01"}).status_code == 403  # no CSRF token
    assert Api(env.app).c.post(url, json={"transaction_date": "2026-09-01"}).status_code in (401, 403)
    assert env.ru.get(f"/api/transactions/{t['id']}").json()["transaction_date"] == "2026-08-01"
    # general PATCH editing of VOID transactions remains blocked (AC-REG-017 unchanged)
    assert env.ru.patch(f"/api/transactions/{t['id']}", {"transaction_date": "2026-09-01"}).status_code == 409


def test_cr001_closed_fiscal_year_protection(env, base):
    from conftest import PDF_BYTES
    fy = base["fy"]["id"]
    t = _zero_void(env, base)
    other = env.fy("2028", "2027-07-01", "2028-06-30")
    env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True})
    env.bm.c.post(f"/api/attachments?owner_type=fiscal_year&owner_id={fy}", files={"file": ("a.pdf", PDF_BYTES)},
                  headers={"X-CSRF-Token": env.bm.csrf})
    assert env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True}).status_code == 200
    # record belongs to the closed year -> immutable
    assert env.ru.post(f"/api/transactions/{t['id']}/void-date", {"transaction_date": "2027-08-01"}).status_code == 409
    # a record in an open year cannot be moved into a closed year's Budget 0
    t2 = _zero_void(env, base, date="2027-08-01")
    assert t2["allocations"][0]["budget"]["fiscal_year"]["id"] == other["id"]
    r = env.ru.post(f"/api/transactions/{t2['id']}/void-date", {"transaction_date": "2026-09-01"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "FISCAL_YEAR_CLOSED"
