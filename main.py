import logging
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import audit
import idempotency
from config import settings
from finnet_client import FinnetAuthError, FinnetPaymentError, finnet
from models import (
    ErrorResponse,
    HealthResponse,
    PaymentRequest,
    PaymentResponse,
    StatusResponse,
)
from security import require_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="API de Impostos — Petlove",
    version="2.0.0",
    description="Integração com Finnet Open Banking V1.2 para pagamento de tributos",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Idempotency-Key"],
    allow_credentials=False,
)

# Dependência reutilizável — injeta API Key validada em todas as rotas protegidas
AuthDep = Annotated[str, Depends(require_api_key)]


def _caller(request: Request) -> str:
    return request.headers.get("origin") or request.client.host or "unknown"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        env=settings.env,
        finnet_base_url=settings.base_url,
    )


# ── Envio de pagamento ────────────────────────────────────────────────────────

@app.post(
    "/payments/submit",
    response_model=PaymentResponse,
    responses={
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_api_key)],
)
def submit_payment(
    body: PaymentRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    caller = _caller(request)

    # Gera chave determinística se o portal não enviou Idempotency-Key
    idem_key = idempotency_key or idempotency.make_key(
        body.barcode, body.amount, body.due_date
    )

    # Bloqueia envio duplicado
    cached = idempotency.get(idem_key)
    if cached:
        audit.log_duplicate_blocked(caller=caller, idempotency_key=idem_key, env=settings.env)
        return PaymentResponse(
            correlation_id=cached,
            message="Pagamento já processado anteriormente (idempotência).",
        )

    audit.log_payment_request(
        caller=caller,
        idempotency_key=idem_key,
        barcode=body.barcode,
        amount=body.amount,
        tribute_code=body.tribute_code,
        taxpayer_cnpj=body.taxpayer_cnpj,
        env=settings.env,
    )

    try:
        correlation_id = finnet.submit_payment(body.model_dump())
        idempotency.register(idem_key, correlation_id)
        audit.log_payment_result(
            caller=caller,
            idempotency_key=idem_key,
            barcode=body.barcode,
            correlation_id=correlation_id,
            status="SUCCESS",
            env=settings.env,
        )
        return PaymentResponse(correlation_id=correlation_id)

    except FinnetAuthError as exc:
        audit.log_payment_result(
            caller=caller, idempotency_key=idem_key, barcode=body.barcode,
            correlation_id=None, status="AUTH_ERROR", error=str(exc), env=settings.env,
        )
        raise HTTPException(status_code=502, detail=str(exc))

    except FinnetPaymentError as exc:
        audit.log_payment_result(
            caller=caller, idempotency_key=idem_key, barcode=body.barcode,
            correlation_id=None, status="PAYMENT_ERROR", error=str(exc), env=settings.env,
        )
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc))


# ── Consulta de status ────────────────────────────────────────────────────────

@app.get(
    "/payments/{correlation_id}/status",
    response_model=StatusResponse,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_key)],
)
def get_status(correlation_id: str):
    try:
        result = finnet.get_payment_status(correlation_id)
        return StatusResponse(
            correlation_id=correlation_id,
            status=result["status"],
            reject_reason=result.get("reject_reason"),
        )
    except FinnetAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except FinnetPaymentError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc))
