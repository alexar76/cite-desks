from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .basepay import USDC_DECIMALS
from .models import BaseInvoice, Brief, DeliveryLog, DeskGrant, PushDevice, Run, UsageEvent, User, Watch, Workspace
from .plans import plan_is_expired

WINDOW_DAYS = 30


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _day(value: datetime | None) -> str | None:
    aware = _aware(value)
    if aware is None:
        return None
    return aware.astimezone(timezone.utc).date().isoformat()


def _usdc(amount_raw: int | None) -> float:
    return round(int(amount_raw or 0) / (10**USDC_DECIMALS), 6)


def _empty_series(days: list[str]) -> dict[str, list]:
    return {
        "days": days,
        "runs": [0] * len(days),
        "invoices": [0] * len(days),
        "paid": [0] * len(days),
        "cogs_usd": [0.0] * len(days),
    }


def dashboard(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    now = _aware(now) or datetime.now(timezone.utc)
    start = now - timedelta(days=WINDOW_DAYS - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    days = [(start + timedelta(days=i)).date().isoformat() for i in range(WINDOW_DAYS)]
    index = {day: i for i, day in enumerate(days)}
    series = _empty_series(days)

    workspaces = db.query(Workspace).all()
    users = db.query(User).all()
    watches = db.query(Watch).all()
    runs = db.query(Run).all()
    invoices = db.query(BaseInvoice).all()
    grants = db.query(DeskGrant).all()
    deliveries = db.query(DeliveryLog).all()
    usage = db.query(UsageEvent).all()
    briefs = db.query(Brief).all()
    devices = db.query(PushDevice).all()

    for run in runs:
        day = _day(run.started_at)
        if day in index and run.status == "completed":
            series["runs"][index[day]] += 1
    for invoice in invoices:
        day = _day(invoice.created_at)
        if day in index:
            series["invoices"][index[day]] += 1
        if invoice.status == "paid":
            paid_day = _day(invoice.paid_at or invoice.created_at)
            if paid_day in index:
                series["paid"][index[paid_day]] += 1
    for event in usage:
        day = _day(event.created_at)
        if day in index:
            series["cogs_usd"][index[day]] = round(series["cogs_usd"][index[day]] + float(event.amount_usd or 0), 4)

    completed = [r for r in runs if r.status == "completed"]
    completed_30 = [r for r in completed if (_aware(r.started_at) or now) >= start]
    cogs_30 = sum(float(e.amount_usd or 0) for e in usage if (_aware(e.created_at) or now) >= start)
    paid_invoices = [i for i in invoices if i.status == "paid"]
    paid_30 = [i for i in paid_invoices if (_aware(i.paid_at or i.created_at) or now) >= start]
    usdc_paid_30 = sum(_usdc(i.amount_raw) for i in paid_30)
    usdc_paid_all = sum(_usdc(i.amount_raw) for i in paid_invoices)

    ws_with_watch = {w.workspace_id for w in watches}
    ws_with_run = {r.workspace_id for r in completed}
    ws_with_alert = {r.workspace_id for r in completed if r.alerted}

    funnel = [
        {"id": "invoice", "label": "Invoice opened", "count": len(invoices)},
        {"id": "paid", "label": "USDC settled", "count": len(paid_invoices)},
        {"id": "grant", "label": "Desk key minted", "count": len(grants)},
        {"id": "redeemed", "label": "Key redeemed", "count": sum(1 for g in grants if g.redeemed_at)},
        {"id": "watch", "label": "First watch", "count": len(ws_with_watch)},
        {"id": "run", "label": "First completed run", "count": len(ws_with_run)},
        {"id": "alert", "label": "Alert fired", "count": len(ws_with_alert)},
    ]
    top = funnel[0]["count"] or 1
    prev = None
    for step in funnel:
        step["of_top_pct"] = round(100 * step["count"] / top, 1) if funnel[0]["count"] else 0.0
        step["of_prev_pct"] = round(100 * step["count"] / prev, 1) if prev else 100.0
        prev = step["count"] or 1

    plan_counts: dict[str, int] = defaultdict(int)
    for ws in workspaces:
        plan_counts[ws.plan or "solo"] += 1
    plans = [{"plan": plan, "workspaces": n} for plan, n in sorted(plan_counts.items())]

    evidence_counts: dict[str, int] = defaultdict(int)
    for run in completed_30:
        evidence_counts[run.evidence_status or "unknown"] += 1
    evidence = [{"status": status, "count": n} for status, n in sorted(evidence_counts.items())]

    delivery_map: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0})
    for row in deliveries:
        bucket = delivery_map[row.channel or "unknown"]
        if row.ok:
            bucket["ok"] += 1
        else:
            bucket["fail"] += 1
    delivery = [{"channel": channel, **counts} for channel, counts in sorted(delivery_map.items())]

    user_counts: dict[str, int] = defaultdict(int)
    owner_email: dict[str, str] = {}
    for user in sorted(users, key=lambda u: _aware(u.created_at) or now):
        user_counts[user.workspace_id] += 1
        owner_email.setdefault(user.workspace_id, user.email)
    watch_counts: dict[str, int] = defaultdict(int)
    last_run: dict[str, datetime | None] = {}
    for watch in watches:
        watch_counts[watch.workspace_id] += 1
        stamp = _aware(watch.last_run_at)
        if stamp and (last_run.get(watch.workspace_id) is None or stamp > last_run[watch.workspace_id]):
            last_run[watch.workspace_id] = stamp
    run_counts: dict[str, int] = defaultdict(int)
    for run in completed:
        run_counts[run.workspace_id] += 1
    cogs_by_ws: dict[str, float] = defaultdict(float)
    for event in usage:
        cogs_by_ws[event.workspace_id] += float(event.amount_usd or 0)
    device_counts: dict[str, int] = defaultdict(int)
    for device in devices:
        device_counts[device.workspace_id] += 1

    workspace_rows = []
    for ws in sorted(workspaces, key=lambda row: _aware(row.created_at) or now, reverse=True):
        workspace_rows.append(
            {
                "id": ws.id,
                "name": ws.name,
                "plan": ws.plan,
                "expired": plan_is_expired(ws),
                "email": owner_email.get(ws.id, ""),
                "users": user_counts.get(ws.id, 0),
                "watches": watch_counts.get(ws.id, 0),
                "runs": run_counts.get(ws.id, 0),
                "cogs_usd": round(cogs_by_ws.get(ws.id, 0.0), 4),
                "push_devices": device_counts.get(ws.id, 0),
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
                "plan_expires_at": ws.plan_expires_at.isoformat() if ws.plan_expires_at else None,
                "last_run_at": last_run[ws.id].isoformat() if last_run.get(ws.id) else None,
            }
        )

    recent_runs = []
    for run in sorted(completed, key=lambda r: _aware(r.started_at) or now, reverse=True)[:20]:
        ws = next((w for w in workspaces if w.id == run.workspace_id), None)
        recent_runs.append(
            {
                "id": run.id,
                "workspace": ws.name if ws else run.workspace_id,
                "status": run.status,
                "evidence_status": run.evidence_status,
                "alerted": run.alerted,
                "cogs_usd": float(run.cogs_usd or 0),
                "started_at": run.started_at.isoformat() if run.started_at else None,
            }
        )

    recent_invoices = []
    for invoice in sorted(invoices, key=lambda i: _aware(i.created_at) or now, reverse=True)[:20]:
        recent_invoices.append(
            {
                "id": invoice.id,
                "plan": invoice.plan,
                "status": invoice.status,
                "amount_usdc": _usdc(invoice.amount_raw),
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            }
        )

    sku_rows = (
        db.query(UsageEvent.sku, func.count(UsageEvent.id), func.coalesce(func.sum(UsageEvent.amount_usd), 0))
        .group_by(UsageEvent.sku)
        .all()
    )

    return {
        "as_of": now.isoformat(),
        "window_days": WINDOW_DAYS,
        "kpis": {
            "workspaces": len(workspaces),
            "users": len(users),
            "watches": len(watches),
            "watches_active": sum(1 for w in watches if w.status == "active"),
            "runs_completed": len(completed),
            "runs_completed_30d": len(completed_30),
            "briefs": len(briefs),
            "cogs_usd_30d": round(cogs_30, 4),
            "usdc_paid_30d": round(usdc_paid_30, 4),
            "usdc_paid": round(usdc_paid_all, 4),
            "invoices_pending": sum(1 for i in invoices if i.status == "pending"),
            "grants_unredeemed": sum(1 for g in grants if not g.redeemed_at),
            "push_devices": len(devices),
        },
        "funnel": funnel,
        "series": series,
        "plans": plans,
        "evidence": evidence,
        "delivery": delivery,
        "by_sku": [
            {"sku": sku, "count": int(count), "cogs_usd": float(total or 0)}
            for sku, count, total in sku_rows
            if sku
        ],
        "workspaces": workspace_rows,
        "recent_runs": recent_runs,
        "recent_invoices": recent_invoices,
    }
