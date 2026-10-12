from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import basepay
from ..db import get_db
from ..models import BaseInvoice
from ..plans import PLANS
from ..security import allow_pay_attempt

router = APIRouter(prefix="/api/public/pay", tags=["pay-public"])


class InvoiceIn(BaseModel):
    plan: str = "solo"
    payment_method: str = "usdc_base"


class ConfirmIn(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)


@router.get("/status")
def pay_rail_status() -> dict:
    return basepay.rail_public()


def _place_order(body: InvoiceIn, request: Request, db: Session) -> dict:
    if body.plan not in PLANS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown plan")
    if body.payment_method != "usdc_base":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "only usdc_base is open")
    if not basepay.rail_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            basepay.rail_closed_reason() or "USDC Base rail is not configured",
        )
    ip = request.client.host if request.client else "unknown"
    if not allow_pay_attempt(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many invoices from this address")
    try:
        invoice = basepay.create_invoice(db, plan=body.plan, payment_method=body.payment_method)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return basepay.invoice_view(invoice, db)


@router.post("/orders")
def create_order(body: InvoiceIn, request: Request, db: Session = Depends(get_db)) -> dict:
    return _place_order(body, request, db)


@router.post("/invoices")
def create_invoice(body: InvoiceIn, request: Request, db: Session = Depends(get_db)) -> dict:
    return _place_order(body, request, db)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, db: Session = Depends(get_db)) -> dict:
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    if invoice.status == "pending" and invoice.expires_at is not None:
        exp = invoice.expires_at if invoice.expires_at.tzinfo else invoice.expires_at.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            invoice.status = "expired"
            db.commit()
    return basepay.invoice_view(invoice, db)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: str, db: Session = Depends(get_db)) -> Response:
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    number = basepay.invoice_number(invoice.id)
    return Response(
        content=basepay.render_invoice_pdf(invoice),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="emberline_{number}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/invoices/{invoice_id}/confirm")
def confirm_invoice(invoice_id: str, body: ConfirmIn, db: Session = Depends(get_db)) -> dict:
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    try:
        invoice = basepay.confirm_invoice(db, invoice, body.tx_hash.strip())
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except basepay.RpcError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return basepay.invoice_view(invoice, db)


@router.post("/invoices/{invoice_id}/simulate")
def simulate_invoice(invoice_id: str, db: Session = Depends(get_db)) -> dict:
    if not basepay.fixture_allowed():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    try:
        invoice = basepay.simulate_payment(db, invoice)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return basepay.invoice_view(invoice, db)
