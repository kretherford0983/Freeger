"""v1.2 CR-004 (no-attachment flag) and CR-005 (Fiscal Year documentation review warnings)."""
from conftest import PDF_BYTES

from fmpoc.services.documentation import Child, classify


def up(env, owner_type, owner_id, client=None):
    c = client or env.ru
    r = c.c.post(f"/api/attachments?owner_type={owner_type}&owner_id={owner_id}", files={"file": ("r.pdf", PDF_BYTES)},
                 headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 201, r.text
    return r.json()


def review(env, fy_id):
    return {i["transaction_id"]: i for i in env.bu.get(f"/api/fiscal-years/{fy_id}/documentation-review").json()["items"]}


def test_cr005_rule_truth_table():
    """Product-owner rule (v1.2.1): a parent attachment or parent indicator exempts the children; otherwise every
    child needs an attachment or its own indicator."""
    none, att, flag = Child(0, False), Child(1, False), Child(0, True)
    # parent has an attachment -> documented, children not reviewed
    assert classify(1, False, [none, none]) is None
    # parent has the indicator -> children not reviewed; listed as a marked item
    assert classify(0, True, [none, none]) == "NO_ATTACHMENT_MARKED"
    # parent neither -> each child needs attachment or indicator
    assert classify(0, False, [att, att]) is None
    assert classify(0, False, [att, none]) == "MISSING_ATTACHMENTS"
    assert classify(0, False, [none, none]) == "MISSING_ATTACHMENTS"
    assert classify(0, False, [att, flag]) == "NO_ATTACHMENT_MARKED"
    assert classify(0, False, [flag, flag]) == "NO_ATTACHMENT_MARKED"
    assert classify(0, False, [flag, none]) == "MISSING_ATTACHMENTS"
    # a normal transaction is the same rule with one child
    assert classify(0, False, [none]) == "MISSING_ATTACHMENTS"
    assert classify(0, False, [att]) is None and classify(1, False, [none]) is None


def test_cr004_no_attachment_flag_create_update_audit(env, base):
    a = base["acct"]["id"]
    t = env.txn(a, "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "1.23", "description": "Interest"}],
                no_attachment=True, no_attachment_reason="Bank interest - direct deposit")
    assert t["no_attachment"] is True and t["no_attachment_reason"] == "Bank interest - direct deposit"
    ev = env.auditor.get(f"/api/audit-events?object_type=register_transaction&object_id={t['id']}").json()["items"]
    assert ev[0]["after"]["no_attachment"] is True
    # clearing the flag via edit
    r = env.ru.patch(f"/api/transactions/{t['id']}", {"no_attachment": False})
    assert r.status_code == 200 and r.json()["no_attachment"] is False and r.json()["no_attachment_reason"] is None
    # setting it on a CLEARED transaction does not require the cleared-edit confirmation (non-financial)
    c = env.txn(a, "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "2.00"}], clear_date="2026-08-02")
    r = env.ru.patch(f"/api/transactions/{c['id']}", {"no_attachment": True, "no_attachment_reason": "ACH"})
    assert r.status_code == 200 and r.json()["no_attachment"] is True
    # ...but a financial edit still does
    assert env.ru.patch(f"/api/transactions/{c['id']}", {"notes": "x"}).status_code == 409
    # read-only roles cannot set it
    assert env.bm.patch(f"/api/transactions/{c['id']}", {"no_attachment": False}).status_code == 403
    assert env.ru.patch(f"/api/transactions/{c['id']}", {"no_attachment": "maybe"}).status_code == 422


def test_cr004_upload_clears_flag(env, base):
    t = env.txn(base["acct"]["id"], "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "5.00"}],
                no_attachment=True, no_attachment_reason="none")
    up(env, "transaction", t["id"])
    t2 = env.ru.get(f"/api/transactions/{t['id']}").json()
    assert t2["no_attachment"] is False
    assert env.auditor.get(f"/api/audit-events?action=TRANSACTION_NO_ATTACHMENT_CLEARED&object_id={t['id']}").json()["total"] == 1


def test_cr005_documentation_review_categories_and_non_blocking(env, base):
    fy = base["fy"]["id"]
    a = base["acct"]["id"]
    p = env.budget(fy, "2000", "Programs", "EXPENSE", "5000.00")
    env.budget(fy, "01", "Supplies", amount="3000.00", parent=p["id"])
    opts = {o["label"]: o["id"] for o in env.selectable(fy, "WITHDRAWAL")}
    split = [{"budget_id": base["exp_leaf"], "amount": "10.00"}, {"budget_id": opts["2000-01 Supplies"], "amount": "5.00"}]
    single_none = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "1.00"}], clear_date="2026-08-02")
    single_parent = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "2.00"}], clear_date="2026-08-02")
    up(env, "transaction", single_parent["id"])
    single_child = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "3.00"}], clear_date="2026-08-02")
    up(env, "allocation", single_child["allocations"][0]["id"])
    split_all_children = env.txn(a, "WITHDRAWAL", split, clear_date="2026-08-02")
    for al in split_all_children["allocations"]:
        up(env, "allocation", al["id"])
    split_parent_only = env.txn(a, "WITHDRAWAL", split, clear_date="2026-08-02")
    up(env, "transaction", split_parent_only["id"])
    split_parent_one_child = env.txn(a, "WITHDRAWAL", split, clear_date="2026-08-02")
    up(env, "transaction", split_parent_one_child["id"])
    up(env, "allocation", split_parent_one_child["allocations"][0]["id"])
    split_one_child = env.txn(a, "WITHDRAWAL", split, clear_date="2026-08-02")
    up(env, "allocation", split_one_child["allocations"][0]["id"])
    child_flag_split = [dict(split[0]), dict(split[1], no_attachment=True, no_attachment_reason="Bank fee")]
    split_child_flag = env.txn(a, "WITHDRAWAL", child_flag_split, clear_date="2026-08-02")
    up(env, "allocation", split_child_flag["allocations"][0]["id"])
    split_parent_flag = env.txn(a, "WITHDRAWAL", split, clear_date="2026-08-02", no_attachment=True,
                                no_attachment_reason="Lost receipt")
    marked = env.txn(a, "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "0.50"}], clear_date="2026-08-02",
                     no_attachment=True, no_attachment_reason="Interest")
    voided = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "9.00"}])
    env.ru.post(f"/api/transactions/{voided['id']}/void", {"reason": "x", "confirm_irreversible": True})

    items = review(env, fy)
    assert items[single_none["id"]]["category"] == "MISSING_ATTACHMENTS"
    assert single_parent["id"] not in items and single_child["id"] not in items
    assert split_all_children["id"] not in items
    assert split_parent_only["id"] not in items  # parent attachment covers the children
    assert split_parent_one_child["id"] not in items
    assert items[split_one_child["id"]]["category"] == "MISSING_ATTACHMENTS"
    assert items[split_one_child["id"]]["allocations_without_documentation"] == [split_one_child["allocations"][1]["id"]]
    assert items[split_child_flag["id"]]["category"] == "NO_ATTACHMENT_MARKED"
    assert items[split_child_flag["id"]]["allocations_marked_no_attachment"] == [split_child_flag["allocations"][1]["id"]]
    assert items[split_parent_flag["id"]]["category"] == "NO_ATTACHMENT_MARKED"
    assert items[split_parent_flag["id"]]["allocations_without_documentation"] == []
    assert items[marked["id"]]["category"] == "NO_ATTACHMENT_MARKED" and items[marked["id"]]["no_attachment_reason"] == "Interest"
    assert voided["id"] not in items  # VOID transactions are not listed
    # warnings (not blockers) in the closure check
    env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True})
    up(env, "fiscal_year", fy, env.bm)
    chk = env.bm.get(f"/api/fiscal-years/{fy}/closure-check").json()
    codes = {w["code"]: w for w in chk["warnings"]}
    assert set(codes["MISSING_ATTACHMENTS"]["transaction_ids"]) == {single_none["id"], split_one_child["id"]}
    assert set(codes["NO_ATTACHMENT_MARKED"]["transaction_ids"]) == {marked["id"], split_child_flag["id"], split_parent_flag["id"]}
    assert chk["blockers"] == [] and chk["can_close"] is True
    assert env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True}).status_code == 200
    # admin cannot read the review (financial data)
    assert env.admin.get(f"/api/fiscal-years/{fy}/documentation-review").status_code == 403


def test_migration_0003_0004_preserve_existing_data(tmp_path):
    """Upgrading a v1.1 database (revision 0002) adds the new columns without touching existing rows."""
    import sqlite3

    from alembic import command

    from fmpoc.db import alembic_config, upgrade_database
    db = tmp_path / "old.sqlite3"
    url = f"sqlite:///{db}"
    command.upgrade(alembic_config(url), "0002_audit_append_only")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO workspace (id, name, created_at, next_entity_number) VALUES (1,'w','2026-01-01',1)")
    con.execute("INSERT INTO bank_account (id, workspace_id, financial_institution_entity_id, account_name, account_type,"
                " account_number_ciphertext, account_number_fingerprint, account_number_visible_suffix, register_enabled,"
                " is_primary, status, created_at, updated_at) VALUES (1,1,1,'a','CHECKING','v1:x','f','1234',1,0,'ACTIVE',"
                "'2026-01-01','2026-01-01')")
    con.execute("INSERT INTO register_transaction (id, workspace_id, bank_account_id, transaction_type, transaction_date,"
                " entry_timestamp, status, created_at, updated_at) VALUES (7,1,1,'DEPOSIT','2026-08-01','2026-08-01',"
                "'ACTIVE','2026-08-01','2026-08-01')")
    con.commit()
    con.close()
    upgrade_database(url)
    con = sqlite3.connect(db)
    row = con.execute("SELECT id, transaction_type, status, transfer_group, no_attachment FROM register_transaction").fetchone()
    ver = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    con.close()
    assert row == (7, "DEPOSIT", "ACTIVE", None, 0)
    assert ver == "0004_allocation_no_attachment"


def test_cr005_allocation_flag_api_and_autoclear(env, base):
    fy = base["fy"]["id"]
    a = base["acct"]["id"]
    p = env.budget(fy, "2000", "Programs", "EXPENSE", "5000.00")
    env.budget(fy, "01", "Supplies", amount="3000.00", parent=p["id"])
    opts = {o["label"]: o["id"] for o in env.selectable(fy, "WITHDRAWAL")}
    t = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "10.00"},
                                  {"budget_id": opts["2000-01 Supplies"], "amount": "5.00", "no_attachment": True,
                                   "no_attachment_reason": "Card fee"}], clear_date="2026-08-02")
    a1, a2 = t["allocations"]
    assert a2["no_attachment"] is True and a2["no_attachment_reason"] == "Card fee" and a1["no_attachment"] is False
    # toggling allocation flags on a CLEARED transaction is not a financial edit (no confirmation)
    body = {"allocations": [{"id": a1["id"], "budget_id": a1["budget_id"], "amount": "10.00", "no_attachment": True},
                            {"id": a2["id"], "budget_id": a2["budget_id"], "amount": "5.00"}]}
    r = env.ru.patch(f"/api/transactions/{t['id']}", body)
    assert r.status_code == 200, r.text
    al = {x["id"]: x for x in r.json()["allocations"]}
    assert al[a1["id"]]["no_attachment"] is True and al[a2["id"]]["no_attachment"] is True  # unchanged when omitted
    # a financial allocation change still needs the cleared-edit confirmation
    body2 = {"allocations": [{"id": a1["id"], "budget_id": a1["budget_id"], "amount": "11.00"},
                             {"id": a2["id"], "budget_id": a2["budget_id"], "amount": "5.00"}]}
    assert env.ru.patch(f"/api/transactions/{t['id']}", body2).status_code == 409
    # uploading to the allocation clears only that allocation's marker
    up(env, "allocation", a1["id"])
    al = {x["id"]: x for x in env.ru.get(f"/api/transactions/{t['id']}").json()["allocations"]}
    assert al[a1["id"]]["no_attachment"] is False and al[a2["id"]]["no_attachment"] is True
    assert env.auditor.get(f"/api/audit-events?action=ALLOCATION_NO_ATTACHMENT_CLEARED&object_id={a1['id']}").json()["total"] == 1
    # an allocation upload does not clear the parent marker (parent marker exempts children)
    t2 = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "1.00"},
                                   {"budget_id": opts["2000-01 Supplies"], "amount": "1.00"}], no_attachment=True)
    up(env, "allocation", t2["allocations"][0]["id"])
    assert env.ru.get(f"/api/transactions/{t2['id']}").json()["no_attachment"] is True
    assert env.ru.patch(f"/api/transactions/{t['id']}", {"allocations": [{"id": a1["id"], "budget_id": a1["budget_id"],
                        "amount": "10.00", "no_attachment": "maybe"}]}).status_code == 422
