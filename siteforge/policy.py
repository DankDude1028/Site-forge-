"""Deterministic, default-deny policy and one-use approval/budget reservations.

An authorization receipt is a durable intent, not a claim that a provider action
occurred. Adapters must pass its idempotency key to the provider and reconcile an
unknown outcome; authorizing the same approval again never issues a second intent.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .contracts import ActionExecution, ActionRequest
from .db import Approval, Budget, Database, Notification, Organization, PolicyDecision, Receipt, Site, Task, audit, utcnow
from .queue import DomainError, aware, digest, tenant_row


AGENT_TOOLS: dict[str, frozenset[str]] = {
    "portfolio_director": frozenset({"read_portfolio", "score_opportunities", "propose_workflow"}),
    "research": frozenset({"read_web", "read_sources", "write_evidence"}),
    "developer": frozenset({"edit_sandbox", "run_tests", "open_pr", "create_preview"}),
    "content": frozenset({"read_sources", "write_draft"}),
    "quality": frozenset({"read_sources", "run_tests", "inspect_preview", "write_quality_report"}),
    "growth": frozenset({"read_analytics", "propose_experiment"}),
    "revenue": frozenset({"read_revenue", "read_costs", "reconcile_ledger"}),
}
RESTRICTED_ACTIONS = frozenset({
    "deploy_preview", "deploy_production", "spend_money", "send_email", "external_outreach", "purchase_domain",
    "affiliate_enrollment", "accept_contract", "change_payment_details", "delete_production_data",
    "change_credentials", "change_privileges", "provision_paid_service",
})
KNOWN_TOOLS = frozenset().union(*AGENT_TOOLS.values())
MONEY_UNIT = Decimal("0.000001")


def money(value: Decimal | str) -> Decimal:
    if isinstance(value, float):
        raise DomainError("money must be a Decimal or decimal string", 422)
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise DomainError("invalid decimal amount", 422) from exc
    exponent = result.as_tuple().exponent
    if not result.is_finite() or not isinstance(exponent, int) or result < 0 or result > Decimal("999999999999.999999") or exponent < -6:
        raise DomainError("money must be finite, nonnegative, and have at most six decimal places", 422)
    return result.quantize(MONEY_UNIT)


def decision(agent_type: str, action: str, *, kill_switch: bool = False) -> tuple[str, str]:
    if agent_type not in AGENT_TOOLS:
        return "denied", "unknown agent"
    if action in RESTRICTED_ACTIONS:
        return ("denied", "kill switch enabled") if kill_switch else ("approval_required", "owner approval required")
    if action not in AGENT_TOOLS[agent_type]:
        return "denied", "tool outside agent contract"
    if kill_switch and action in {"open_pr", "create_preview"}:
        return "denied", "kill switch enabled"
    return "allowed", "bounded contract capability"


def action_hash(action: str, payload: dict[str, Any], site_id: str,
                amount: Decimal, currency: str) -> str:
    return digest({"action": action, "payload": payload, "site_id": site_id,
                   "amount": format(money(amount), ".6f"), "currency": currency})


class PolicyService:
    def __init__(self, db: Database, *, clock: Callable[[], datetime] = utcnow):
        self.db, self.clock = db, clock

    def evaluate(self, org_id: str, agent_type: str, action: str, actor: str = "agent") -> dict[str, str]:
        with self.db.transaction() as session:
            org = session.get(Organization, org_id)
            if org is None:
                raise DomainError("organization not provisioned", 403)
            outcome, reason = decision(agent_type, action, kill_switch=org.kill_switch)
            session.add(PolicyDecision(org_id=org_id, action=action, outcome=outcome,
                                       reason=reason, context={"agent_type": agent_type}))
            audit(session, org_id, actor, "policy.evaluate", action, outcome, reason=reason)
            return {"outcome": outcome, "reason": reason}

    def request_approval(self, org_id: str, request: ActionRequest, requester: str) -> dict[str, Any]:
        if request.action not in RESTRICTED_ACTIONS:
            raise DomainError("approval only supports known restricted actions", 422)
        bound_hash = action_hash(request.action, request.payload, str(request.site_id), request.amount, request.currency)
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            tenant_row(session, Site, org_id, str(request.site_id))
            if request.task_id:
                task = tenant_row(session, Task, org_id, str(request.task_id))
                if task.site_id != str(request.site_id):
                    raise DomainError("approval task and site differ", 422)
            existing = session.scalar(select(Approval).where(Approval.org_id == org_id,
                                                             Approval.idempotency_key == request.idempotency_key))
            if existing:
                if (existing.payload_hash != bound_hash or existing.request_hash != digest(request.model_dump(mode="json")) or existing.requester != requester
                        or existing.task_id != (str(request.task_id) if request.task_id else None)):
                    raise DomainError("approval idempotency key is bound to a different request")
                return self._approval(existing)
            approval = Approval(org_id=org_id, site_id=str(request.site_id),
                                task_id=str(request.task_id) if request.task_id else None,
                                agent_type=request.agent_type.value, action=request.action,
                                payload=request.payload, payload_hash=bound_hash,
                                request_hash=digest(request.model_dump(mode="json")), amount=money(request.amount),
                                currency=request.currency, requester=requester,
                                idempotency_key=request.idempotency_key,
                                expires_at=self.clock() + timedelta(seconds=request.expires_in_seconds))
            session.add(approval)
            session.flush()
            audit(session, org_id, requester, "approval.request", approval.id, payload_hash=bound_hash)
            return self._approval(approval)

    @staticmethod
    def _approval(approval: Approval) -> dict[str, Any]:
        return {key: getattr(approval, key) for key in (
            "id", "site_id", "task_id", "agent_type", "action", "payload", "payload_hash", "amount",
            "currency", "requester", "status", "expires_at", "approved_by", "decided_at", "reason")}

    def decide(self, org_id: str, approval_id: str, approver: str, approve: bool,
               reason: str = "") -> dict[str, Any]:
        with self.db.transaction() as session:
            approval = tenant_row(session, Approval, org_id, approval_id, lock=True)
            desired = "approved" if approve else "rejected"
            if approval.status == desired and approval.approved_by == approver:
                return self._approval(approval)
            if approval.status != "pending":
                raise DomainError("approval already decided")
            if aware(approval.expires_at) <= self.clock():
                raise DomainError("approval expired")
            approval.status, approval.approved_by = desired, approver
            approval.decided_at, approval.reason = self.clock(), reason[:500]
            audit(session, org_id, approver, "approval." + desired, approval.id,
                  payload_hash=approval.payload_hash)
            return self._approval(approval)

    def set_budget(self, org_id: str, period: str, limit: Decimal | str,
                   actor: str, currency: str = "USD") -> dict[str, Any]:
        if period not in {self.clock().strftime("%Y-%m"), self.clock().strftime("%Y-%m-%d")}:
            raise DomainError("budget period must be the current UTC day or month", 422)
        limit = money(limit)
        with self.db.transaction() as session:
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            budget = session.scalar(select(Budget).where(Budget.org_id == org_id, Budget.period == period,
                                                        Budget.currency == currency).with_for_update())
            if budget is None:
                budget = Budget(org_id=org_id, period=period, currency=currency, limit_amount=limit,
                                used_amount=Decimal("0"), reserved_amount=Decimal("0"))
                session.add(budget)
            elif budget.used_amount + budget.reserved_amount > limit:
                raise DomainError("budget below committed spend")
            else:
                budget.limit_amount = limit
            session.flush()
            self._budget_alerts(session, budget)
            audit(session, org_id, actor, "budget.configure", period, amount=str(limit), currency=currency)
            return {"period": period, "currency": currency, "limit_amount": limit}

    def has_budget(self, org_id: str, period: str, currency: str = "USD") -> bool:
        with self.db.transaction() as session:
            return session.scalar(select(Budget.id).where(Budget.org_id == org_id, Budget.period == period,
                                                          Budget.currency == currency)) is not None

    @staticmethod
    def _budget_alerts(session: Session, budget: Budget) -> None:
        """Persist threshold notices once under the caller's organization lock.

        Reserved commitments count toward a cap; a notice does not claim realized
        provider expense. Notices remain internal drafts, with no message delivery.
        """
        committed = budget.used_amount + budget.reserved_amount
        if budget.limit_amount <= 0:
            return
        for threshold in (50, 80, 100):
            if committed * 100 < budget.limit_amount * threshold:
                continue
            kind = f"budget.threshold.{threshold}"
            existing = session.scalar(select(Notification.id).where(
                Notification.org_id == budget.org_id, Notification.kind == kind,
                Notification.data["budget_id"].as_string() == budget.id))
            if existing is not None:
                continue
            session.add(Notification(org_id=budget.org_id, kind=kind, status="draft", data={
                "budget_id": budget.id, "period": budget.period, "currency": budget.currency,
                "threshold_percent": threshold, "limit_amount": str(budget.limit_amount),
                "used_amount": str(budget.used_amount), "reserved_amount": str(budget.reserved_amount),
                "basis": "used_plus_reserved_commitments", "external_delivery": False,
            }))
            audit(session, budget.org_id, "policy", "budget.threshold", budget.id,
                  threshold_percent=threshold, period=budget.period, currency=budget.currency)

    def _reserve(self, session: Session, org_id: str, amount: Decimal, currency: str,
                 task_id: str | None) -> list[str]:
        if amount == 0:
            return []
        periods = [self.clock().strftime("%Y-%m"), self.clock().strftime("%Y-%m-%d")]
        budgets = session.scalars(select(Budget).where(Budget.org_id == org_id, Budget.currency == currency,
                                                       Budget.period.in_(periods)).order_by(Budget.period)
                                  .with_for_update()).all()
        if len(budgets) != 2:
            raise DomainError("external spend defaults to zero; daily and monthly limits required", 403)
        for budget in budgets:
            if budget.used_amount + budget.reserved_amount + amount > budget.limit_amount:
                raise DomainError("budget ceiling exceeded", 403)
        if task_id:
            task = tenant_row(session, Task, org_id, task_id, lock=True)
            pending = session.scalars(select(Receipt).join(Approval, Receipt.approval_id == Approval.id)
                                     .where(Approval.task_id == task_id, Receipt.status.in_(["reserved", "unknown"]))).all()
            if task.actual_cost + sum((receipt.amount for receipt in pending), Decimal("0")) + amount > task.budget_cap:
                raise DomainError("per-task budget ceiling exceeded", 403)
        for budget in budgets:
            budget.reserved_amount += amount
            self._budget_alerts(session, budget)
        return periods

    def authorize(self, org_id: str, approval_id: str, execution: ActionExecution,
                  actor: str) -> dict[str, Any]:
        bound_hash = action_hash(execution.action, execution.payload, str(execution.site_id), execution.amount, execution.currency)
        with self.db.transaction() as session:
            # Org lock makes kill-switch activation and budget/receipt creation atomic.
            org = session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            if org is None:
                raise DomainError("organization not provisioned", 403)
            approval = tenant_row(session, Approval, org_id, approval_id, lock=True)
            if approval.payload_hash != bound_hash:
                raise DomainError("approval does not bind this exact action/site/amount/payload", 403)
            existing = session.scalar(select(Receipt).where(Receipt.org_id == org_id,
                                                            Receipt.idempotency_key == execution.idempotency_key))
            if existing:
                if existing.approval_id != approval_id or existing.payload_hash != bound_hash:
                    raise DomainError("receipt idempotency key already bound")
                return self._receipt(existing, replay=True)
            if org.kill_switch:
                raise DomainError("kill switch enabled", 403)
            if approval.status != "approved" or not approval.approved_by:
                raise DomainError("unconsumed owner approval required", 403)
            if aware(approval.expires_at) <= self.clock():
                raise DomainError("approval expired", 403)
            # Recheck persisted payload as well as the supplied binding.
            if action_hash(approval.action, approval.payload, approval.site_id, approval.amount, approval.currency) != approval.payload_hash:
                raise DomainError("approval payload integrity failure", 403)
            periods = self._reserve(session, org_id, approval.amount, approval.currency, approval.task_id)
            receipt = Receipt(org_id=org_id, approval_id=approval_id,
                              idempotency_key=execution.idempotency_key, action=approval.action,
                              payload_hash=bound_hash, amount=approval.amount,
                              currency=approval.currency, budget_periods=periods, status="reserved")
            session.add(receipt)
            approval.status = "consumed"
            session.flush()
            audit(session, org_id, actor, "action.reserve", receipt.id, approval_id=approval_id,
                  payload_hash=bound_hash, amount=str(approval.amount), currency=approval.currency)
            return self._receipt(receipt)

    @staticmethod
    def _receipt(receipt: Receipt, replay: bool = False) -> dict[str, Any]:
        return {"id": receipt.id, "approval_id": receipt.approval_id, "status": receipt.status,
                "idempotency_key": receipt.idempotency_key, "payload_hash": receipt.payload_hash,
                "amount": receipt.amount, "currency": receipt.currency,
                "provider_reference": receipt.provider_reference, "replay": replay,
                "instruction": "Reconcile provider state before retrying an unknown outcome; this is an authorization intent."}

    def reconcile(self, org_id: str, receipt_id: str, status: str, provider_reference: str,
                  actor: str, actual_amount: Decimal | str | None = None) -> dict[str, Any]:
        """Release the reservation; a success books the measured amount when supplied.

        A measured amount may exceed the authorization only if the provider billed more
        than the approved bound; it is booked as billed and flagged in the audit trail.
        """
        if status not in {"succeeded", "failed", "unknown"} or not provider_reference:
            raise DomainError("reconciliation requires an outcome and provider reference", 422)
        if actual_amount is not None and status != "succeeded":
            raise DomainError("only a succeeded outcome books a measured amount", 422)
        measured = None if actual_amount is None else money(actual_amount)
        with self.db.transaction() as session:
            session.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            receipt = tenant_row(session, Receipt, org_id, receipt_id, lock=True)
            if receipt.status in {"succeeded", "failed"}:
                if receipt.status != status or receipt.provider_reference != provider_reference:
                    raise DomainError("final receipt cannot be rewritten")
                return self._receipt(receipt, replay=True)
            booked = receipt.amount if measured is None else measured
            if status != "unknown":
                budgets = session.scalars(select(Budget).where(Budget.org_id == org_id,
                                                               Budget.currency == receipt.currency,
                                                               Budget.period.in_(receipt.budget_periods))
                                          .order_by(Budget.period).with_for_update()).all()
                for budget in budgets:
                    budget.reserved_amount -= receipt.amount
                    if status == "succeeded":
                        budget.used_amount += booked
                        self._budget_alerts(session, budget)
                approval = tenant_row(session, Approval, org_id, receipt.approval_id)
                if status == "succeeded" and approval.task_id:
                    task = tenant_row(session, Task, org_id, approval.task_id, lock=True)
                    task.actual_cost += booked
            receipt.status, receipt.provider_reference = status, provider_reference
            audit(session, org_id, actor, "action.reconcile", receipt.id, outcome=status,
                  provider_reference=provider_reference,
                  **({} if status != "succeeded" else {
                      "booked_amount": str(booked), "authorized_amount": str(receipt.amount),
                      "exceeded_authorization": booked > receipt.amount}))
            return self._receipt(receipt)
