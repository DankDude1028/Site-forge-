"""Decimal ledger ingestion with explicit verification and coverage boundaries."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from sqlalchemy import select

from .db import Database, Expense, Organization, RevenueEvent, Site, audit
from .queue import DomainError, tenant_row


class EconomicsService:
    def __init__(self, db: Database):
        self.db = db

    def record(self, org_id: str, site_id: str, *, provider: str, external_ref: str,
               amount: Decimal | str, currency: str, occurred_at: datetime,
               verification_status: str = "verified", expense: bool = False,
               actor: str = "revenue") -> str:
        if isinstance(amount, float):
            raise DomainError("use decimal strings for money", 422)
        try:
            amount = Decimal(amount)
        except InvalidOperation as exc:
            raise DomainError("invalid decimal amount", 422) from exc
        exponent = amount.as_tuple().exponent
        if not amount.is_finite() or not isinstance(exponent, int) or exponent < -6 or abs(amount) > Decimal("999999999999.999999"):
            raise DomainError("invalid decimal amount", 422)
        if len(currency) != 3 or not currency.isalpha() or currency != currency.upper():
            raise DomainError("ISO currency required", 422)
        if verification_status not in {"verified", "estimated", "pending"}:
            raise DomainError("unknown verification status", 422)
        if occurred_at.tzinfo is None:
            raise DomainError("occurred_at must include timezone", 422)
        model = Expense if expense else RevenueEvent
        with self.db.transaction() as session:
            session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            tenant_row(session, Site, org_id, site_id, lock=True)
            row = cast(Expense | RevenueEvent | None, session.scalar(select(model).where(
                model.org_id == org_id, model.provider == provider, model.external_ref == external_ref)))
            if row is not None:
                if (row.amount != amount or row.currency != currency or row.site_id != site_id
                        or row.verification_status != verification_status):
                    raise DomainError("external ledger reference conflicts with stored record")
                return row.id
            row = model(org_id=org_id, site_id=site_id, provider=provider, external_ref=external_ref,
                        amount=amount, currency=currency, occurred_at=occurred_at,
                        verification_status=verification_status)
            session.add(row)
            session.flush()
            audit(session, org_id, actor, "expense.record" if expense else "revenue.record", row.id,
                  amount=str(amount), currency=currency, verification_status=verification_status)
            return row.id

    def summary(self, org_id: str, site_id: str, currency: str = "USD") -> dict[str, Any]:
        with self.db.session() as session:
            tenant_row(session, Site, org_id, site_id)
            revenue = session.scalars(select(RevenueEvent).where(RevenueEvent.org_id == org_id,
                RevenueEvent.site_id == site_id, RevenueEvent.currency == currency)).all()
            expenses = session.scalars(select(Expense).where(Expense.org_id == org_id,
                Expense.site_id == site_id, Expense.currency == currency)).all()
            verified_rows = [r for r in revenue if r.verification_status == "verified"]
            estimate_rows = [r for r in revenue if r.verification_status == "estimated"]
            cost_rows = [r for r in expenses if r.verification_status == "verified"]
            verified = sum((r.amount for r in verified_rows), Decimal("0"))
            estimated = sum((r.amount for r in estimate_rows), Decimal("0"))
            costs = sum((r.amount for r in cost_rows), Decimal("0"))
            return {"currency": currency, "verified_revenue": verified if verified_rows else None,
                    "estimated_revenue": estimated if estimate_rows else None,
                    "verified_expenses": costs if cost_rows else None,
                    "operating_contribution": verified - costs if verified_rows and cost_rows else None,
                    "coverage": "partial" if revenue or expenses else "missing",
                    "warnings": ["Provider coverage must be reconciled; missing imports are not zero revenue."]}
