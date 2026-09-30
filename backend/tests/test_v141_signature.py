"""v1.4.1 CR-016: audit review signature page."""
import io

from pypdf import PdfReader

from fmpoc.services import signatures as sig


def _text(pdf: bytes) -> str:
    return " ".join(" ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages).split())


def _last_page(pdf: bytes) -> str:
    r = PdfReader(io.BytesIO(pdf))
    return " ".join((r.pages[-1].extract_text() or "").split())


def _person(env, name):
    return env.entity(name, etype="INDIVIDUAL")


def test_variables_and_validation(env, base):
    assert sig.normalize("  a {FY} b {ORG} c {FYE}\r\n") == "a {FY} b {ORG} c {FYE}"
    r = env.bm.post("/api/reports/signature-templates", {"text": "Hello {YEAR} and {org}"})
    assert r.status_code == 422 and "{YEAR}" in r.json()["error"]["message"] and "{org}" in r.json()["error"]["message"]
    fy = base["fy"]["id"]
    r = env.bm.get(f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true&signature_text=Bad+%7BX%7D")
    assert r.status_code == 422


def test_templates_shared_limit_delete_audit(env, base):
    t = env.bm.get("/api/reports/signature-templates").json()
    assert t["default"]["text"] == sig.DEFAULT_TEXT and t["saved"] == [] and t["max_saved"] == 4
    ids = []
    for i in range(4):
        r = env.bm.post("/api/reports/signature-templates", {"text": f"Wording {i} for {{ORG}}"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    # same text again returns the existing one (no duplicate, no limit error)
    assert env.bm.post("/api/reports/signature-templates", {"text": "Wording 0 for {ORG}"}).json()["id"] == ids[0]
    r = env.bm.post("/api/reports/signature-templates", {"text": "A fifth"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "SIGNATURE_TEMPLATE_LIMIT"
    # shared across the organization: another user sees and can delete them
    assert len(env.ru.get("/api/reports/signature-templates").json()["saved"]) == 4
    assert env.ru.delete(f"/api/reports/signature-templates/{ids[1]}").status_code == 200
    assert env.bm.post("/api/reports/signature-templates", {"text": "A fifth"}).status_code == 201
    # the built-in default is not saved as a copy and cannot be deleted
    r = env.bm.post("/api/reports/signature-templates", {"text": sig.DEFAULT_TEXT})
    assert r.status_code == 409
    assert env.bm.delete("/api/reports/signature-templates/99999").status_code == 404
    ev = env.auditor.get("/api/audit-events?action=SIGNATURE_TEMPLATE_SAVED").json()
    assert ev["total"] == 5
    assert env.auditor.get("/api/audit-events?action=SIGNATURE_TEMPLATE_DELETED").json()["total"] == 1
    # administrators have no access to financial reports
    assert env.admin.get("/api/reports/signature-templates").status_code == 403


def test_signature_page_default_wording_and_signers(env, base):
    fy = base["fy"]["id"]
    a, b = _person(env, "Jane Doe"), _person(env, "John Roe")
    url = (f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true&signer_id={a['id']}&signer_title=Trustee"
           f"&signer_id={b['id']}&signer_title=")
    r = env.auditor.get(url)
    assert r.status_code == 200, r.text
    last = _last_page(r.content)
    assert "We, the undersigned" in last
    assert "Acme Org" in last and "July 1, 2026 – June 30, 2027" in last and "as of June 30, 2027" in last
    assert "{" not in last
    assert "Jane Doe, Trustee" in last and "John Roe" in last and "John Roe," not in last
    assert "Date" in last and "Audit review signatures" in last
    ev = env.auditor.get("/api/audit-events?action=REPORT_GENERATED").json()["items"][0]
    assert ev["after"]["signature_page"] == {"wording": "default", "signers": 2}
    # without the option the report is unchanged (no signature page)
    plain = env.auditor.get(f"/api/reports/audit?fiscal_year_id={fy}")
    assert "We, the undersigned" not in _text(plain.content)


def test_signature_page_saved_and_custom_wording(env, base):
    fy = base["fy"]["id"]
    saved = env.bm.post("/api/reports/signature-templates",
                        {"text": "We, the Trustees of {ORG}, approve the records for {FY}.\n\nSecond paragraph ends {FYE}."}).json()
    r = env.bm.get(f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true&signature_template_id={saved['id']}")
    last = _last_page(r.content)
    assert "We, the Trustees of Acme Org, approve the records for July 1, 2026 – June 30, 2027." in last
    assert "Second paragraph ends June 30, 2027." in last
    assert "Name and title" in last  # no signers selected -> blank lines
    r = env.bm.get(f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true&signature_text=Custom+%7BORG%7D+text")
    assert "Custom Acme Org text" in _last_page(r.content)
    # unknown saved id
    assert env.bm.get(f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true&signature_template_id=999").status_code == 422


def test_signers_validation(env, base):
    fy = base["fy"]["id"]
    org = env.entity("Some Org")
    people = [_person(env, f"Person {i}") for i in range(6)]
    q = f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true"
    assert env.bm.get(q + f"&signer_id={org['id']}").status_code == 422  # organizations cannot sign
    assert env.bm.get(q + "".join(f"&signer_id={p['id']}" for p in people)).status_code == 422  # max 5
    assert env.bm.get(q + f"&signer_id={people[0]['id']}&signer_id={people[0]['id']}").status_code == 422
    assert env.bm.get(q + f"&signer_id={people[0]['id']}&signer_title={'x' * 61}").status_code == 422
    env.ru.post(f"/api/entities/{people[1]['id']}/inactivate", {})
    assert env.bm.get(q + f"&signer_id={people[1]['id']}").status_code == 422  # inactive
    five = "".join(f"&signer_id={p['id']}&signer_title=Trustee" for p in [people[0], *people[2:6]])
    r = env.bm.get(q + five)
    assert r.status_code == 200
    last = _last_page(r.content)
    assert all(f"Person {i}, Trustee" in last for i in (0, 2, 3, 4, 5))


def test_signature_text_is_not_markup(env, base):
    fy = base["fy"]["id"]
    r = env.bm.get(f"/api/reports/audit?fiscal_year_id={fy}&signature_page=true"
                   "&signature_text=%3Cimg+src%3D%22%2Fetc%2Fpasswd%22%2F%3E+%3Cb%3Ebold%3C%2Fb%3E")
    assert r.status_code == 200
    assert '<img src="/etc/passwd"/> <b>bold</b>' in _last_page(r.content)
