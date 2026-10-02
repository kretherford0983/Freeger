"""v1.3 CR-009 (split attachment labels) and CR-010 (parent and child attachments on the same split)."""
import io

from conftest import PDF_BYTES, png_bytes
from pypdf import PdfReader


def up(env, owner_type, owner_id, name="doc.pdf", data=PDF_BYTES):
    r = env.ru.c.post(f"/api/attachments?owner_type={owner_type}&owner_id={owner_id}", files={"file": (name, data)},
                      headers={"X-CSRF-Token": env.ru.csrf})
    assert r.status_code == 201, r.text
    return r.json()


def split_deposit(env, base, donor, other):
    return env.txn(base["acct"]["id"], "DEPOSIT", [
        {"budget_id": base["inc_leaf"], "amount": "40.00", "entity_id": donor["id"]},
        {"budget_id": base["inc_leaf"], "amount": "10.00", "entity_id": other["id"]}])


def test_cr010_parent_and_children_attachments_in_both_orders(env, base):
    donor, other = env.entity("Bob Smith", "INDIVIDUAL"), env.entity("Ann Lee", "INDIVIDUAL")
    # children first, then the parent
    t1 = split_deposit(env, base, donor, other)
    for al in t1["allocations"]:
        up(env, "allocation", al["id"], "child.png", png_bytes())
    up(env, "transaction", t1["id"], "deposit-slip.pdf")
    # parent first, then children
    t2 = env.txn(base["acct"]["id"], "DEPOSIT", [
        {"budget_id": base["inc_leaf"], "amount": "41.00", "entity_id": donor["id"]},
        {"budget_id": base["inc_leaf"], "amount": "11.00", "entity_id": other["id"]}])
    up(env, "transaction", t2["id"], "deposit-slip.pdf")
    for al in t2["allocations"]:
        up(env, "allocation", al["id"], "child.pdf")
    for t in (t1, t2):
        got = env.ru.get(f"/api/transactions/{t['id']}").json()
        assert got["attachment_count"] >= 1
        assert all(a["attachment_count"] == 1 for a in got["allocations"])
        assert len(env.ru.get(f"/api/attachments?owner_type=transaction&owner_id={t['id']}").json()) == 1
    # CR-005 unchanged: documented, so neither appears in the documentation review
    items = env.bu.get(f"/api/fiscal-years/{base['fy']['id']}/documentation-review").json()["items"]
    assert {i["transaction_id"] for i in items}.isdisjoint({t1["id"], t2["id"]})


def test_cr009_pdf_uses_entity_budget_labels(env, base):
    donor, other = env.entity("Bob Smith", "INDIVIDUAL"), env.entity("Ann Lee", "INDIVIDUAL")
    t = split_deposit(env, base, donor, other)
    up(env, "allocation", t["allocations"][0]["id"], "bob.pdf")
    up(env, "allocation", t["allocations"][1]["id"], "ann.pdf")
    # withdrawal split: allocations have no entity of their own -> the payee is used
    payee = env.entity("Paper Co")
    w = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "3.00"},
                                                    {"budget_id": base["exp_leaf"], "amount": "4.00"}],
                entity_id=payee["id"])
    up(env, "allocation", w["allocations"][0]["id"], "paper.pdf")
    pdf = env.bu.get(f"/api/reports/audit?fiscal_year_id={base['fy']['id']}").content
    text = " ".join(" ".join((p.extract_text() or "").split()) for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "(Bob Smith - 4000 Donations)" in text and "(Ann Lee - 4000 Donations)" in text
    assert "(Paper Co - 1000 Operations)" in text
    assert "(allocation" not in text
