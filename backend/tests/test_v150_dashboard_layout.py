"""v1.5.0 CR-031: dashboard section order and visibility, saved per user."""
from fmpoc.services.dashboard_layout import SECTIONS

DEFAULT = [{"key": k, "visible": True} for k in SECTIONS]


def test_default_layout_and_save(env):
    me = env.bu.get("/api/auth/me").json()
    assert me["dashboard_layout"] == DEFAULT and me["dashboard_layout_customized"] is False
    want = [{"key": "charts", "visible": True}, {"key": "bank", "visible": False}, {"key": "fiscal_year", "visible": True}]
    r = env.bu.put("/api/me/preferences", {"dashboard_layout": want})
    assert r.status_code == 200
    expected = want + [{"key": k, "visible": True} for k in SECTIONS if k not in ("charts", "bank", "fiscal_year")]
    assert r.json()["dashboard_layout"] == expected and r.json()["dashboard_layout_customized"] is True
    assert env.bu.get("/api/auth/me").json()["dashboard_layout"] == expected
    # per user: others keep the default
    assert env.ru.get("/api/auth/me").json()["dashboard_layout"] == DEFAULT
    # other preferences do not touch the layout
    env.bu.put("/api/me/preferences", {"theme": "dark"})
    assert env.bu.get("/api/auth/me").json()["dashboard_layout"] == expected
    # reset to default
    r = env.bu.put("/api/me/preferences", {"reset_dashboard_layout": True})
    assert r.json()["dashboard_layout"] == DEFAULT and r.json()["dashboard_layout_customized"] is False


def test_layout_validation_and_duplicates(env):
    assert env.auditor.put("/api/me/preferences", {"dashboard_layout": [{"key": "nope", "visible": True}]}).status_code == 422
    assert env.auditor.put("/api/me/preferences", {"dashboard_layout": [{"key": "bank"}]}).status_code == 422
    r = env.auditor.put("/api/me/preferences", {"dashboard_layout": [
        {"key": "review", "visible": True}, {"key": "review", "visible": False}]})
    assert r.status_code == 200 and r.json()["dashboard_layout"][0] == {"key": "review", "visible": True}
    assert [x["key"] for x in r.json()["dashboard_layout"]].count("review") == 1


def test_stored_layout_tolerates_unknown_and_missing_keys():
    from fmpoc.services.dashboard_layout import layout_for

    class U:
        dashboard_layout = "-charts,gone,bank,-bank"
    out = layout_for(U())
    assert out[0] == {"key": "charts", "visible": False} and out[1] == {"key": "bank", "visible": True}
    assert [x["key"] for x in out] == ["charts", "bank"] + [k for k in SECTIONS if k not in ("charts", "bank")]
