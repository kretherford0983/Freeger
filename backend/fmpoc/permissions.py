"""Role -> permission mapping (docs/04 §2 permission matrix). Backend authorization is authoritative."""
from __future__ import annotations

ADMINISTRATOR = "ADMINISTRATOR"
BUDGET_MANAGER = "BUDGET_MANAGER"
BUDGET_USER = "BUDGET_USER"
REGISTER_USER = "REGISTER_USER"
AUDITOR = "AUDITOR"

ROLE_DEFS = [
    (ADMINISTRATOR, "Administrator", "ADMINISTRATOR"),
    (BUDGET_MANAGER, "Budget Manager", "FINANCIAL"),
    (BUDGET_USER, "Budget User", "FINANCIAL"),
    (REGISTER_USER, "Register User", "FINANCIAL"),
    (AUDITOR, "Auditor", "AUDITOR"),
]
ROLE_DOMAIN = {code: domain for code, _n, domain in ROLE_DEFS}
FINANCIAL_ROLES = {BUDGET_MANAGER, BUDGET_USER, REGISTER_USER}

PERMISSIONS: dict[str, set[str]] = {
    "users.view": {ADMINISTRATOR, AUDITOR},
    "users.manage": {ADMINISTRATOR},
    "audit.view": {ADMINISTRATOR, AUDITOR},
    "audit.view_financial_snapshots": {AUDITOR},
    "financial.view": {BUDGET_MANAGER, BUDGET_USER, REGISTER_USER, AUDITOR},
    "fiscal_year.manage": {BUDGET_MANAGER},
    "budget.manage": {BUDGET_MANAGER},
    "bank_account.manage": {BUDGET_MANAGER},
    "bank_account.reveal": {BUDGET_MANAGER},
    "transaction.manage": {REGISTER_USER},
    "entity.manage": {BUDGET_MANAGER, REGISTER_USER},
    "entity.create_financial_institution": {BUDGET_MANAGER, REGISTER_USER},
    "entity.manage_financial_institution": {BUDGET_MANAGER},
    "review.resolve": {BUDGET_MANAGER, REGISTER_USER},
}


def permissions_for(role_codes: set[str]) -> set[str]:
    return {p for p, roles in PERMISSIONS.items() if roles & role_codes}


def validate_role_set(domain: str, role_codes: set[str]) -> str | None:
    """BR-002: returns an error message when the combination crosses security domains."""
    if not role_codes:
        return "At least one role is required."
    unknown = role_codes - set(ROLE_DOMAIN)
    if unknown:
        return "Unknown role."
    domains = {ROLE_DOMAIN[r] for r in role_codes}
    if len(domains) > 1:
        return "Roles from different security domains (Administrator, Financial, Auditor) cannot be combined."
    if domains != {domain}:
        return "Roles do not match the user's security domain."
    return None
