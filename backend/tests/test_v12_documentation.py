"""v1.2 CR-004 (no-attachment flag) and CR-005 (Fiscal Year documentation review warnings)."""
from conftest import PDF_BYTES

from fmpoc.services.documentation import is_documented, split_is_documented


def up(env, owner_type, owner_id, client=None):
    c = client or env.ru
    r = c.c.post(f"/api/attachments?owner_type={owner_type}&owner_id={owner_id}", files={"file": ("r.pdf", PDF_BYTES)},
                 headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 201, r.text
    return r.json()


def review(env, fy_id):
    return {i["transaction_id"]: i for i in env.bu.get(f"/api/fiscal-years/{fy_id}/documentation-review").json()["items"]}


def test_cr005_rule_truth_table():
    # single allocation: parent or the allocation may carry the document
    assert not is_documented(0, [0]) and is_documented(1, [0]) and is_documented(0, [1])
    # split: every child documented -> parent not required
    assert split_is_documented(0, [1, 1, 2])
    # split: parent has none and not every child documented -> missing
    assert not split_is_documented(0, [1, 0]) and not split_is_documented(0, [0, 0])
    # split: no child documented -> missing even with a parent attachment
    assert not split_is_documented(2, [0, 0])
    # split: parent documented and at least one child documented -> ok
    assert split_is_documented(1, [1, 0])


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
    marked = env.txn(a, "DEPOSIT", [{"budget_id": base["inc_leaf"], "amount": "0.50"}], clear_date="2026-08-02",
                     no_attachment=True, no_attachment_reason="Interest")
    voided = env.txn(a, "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "9.00"}])
    env.ru.post(f"/api/transactions/{voided['id']}/void", {"reason": "x", "confirm_irreversible": True})

    items = review(env, fy)
    assert items[single_none["id"]]["category"] == "MISSING_ATTACHMENTS"
    assert single_parent["id"] not in items and single_child["id"] not in items
    assert split_all_children["id"] not in items
    assert items[split_parent_only["id"]]["category"] == "MISSING_ATTACHMENTS"
    assert split_parent_one_child["id"] not in items
    assert items[split_one_child["id"]]["category"] == "MISSING_ATTACHMENTS"
    assert items[split_one_child["id"]]["allocations_without_attachment"] == [split_one_child["allocations"][1]["id"]]
    assert items[marked["id"]]["category"] == "NO_ATTACHMENT_MARKED" and items[marked["id"]]["no_attachment_reason"] == "Interest"
    assert voided["id"] not in items  # VOID transactions are not listed
    # warnings (not blockers) in the closure check
    env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True})
    up(env, "fiscal_year", fy, env.bm)
    chk = env.bm.get(f"/api/fiscal-years/{fy}/closure-check").json()
    codes = {w["code"]: w for w in chk["warnings"]}
    assert set(codes["MISSING_ATTACHMENTS"]["transaction_ids"]) == {single_none["id"], split_parent_only["id"], split_one_child["id"]}
    assert codes["NO_ATTACHMENT_MARKED"]["transaction_ids"] == [marked["id"]]
    assert chk["blockers"] == [] and chk["can_close"] is True
    assert env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True}).status_code == 200
    # admin cannot read the review (financial data)
    assert env.admin.get(f"/api/fiscal-years/{fy}/documentation-review").status_code == 403


def test_migration_0003_preserves_existing_data(tmp_path):
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
    assert ver == "0003_transfers_no_attachment"
