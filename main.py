import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from finnet_client import FinnetAuthError, FinnetPaymentError, finnet
from models import (
    ErrorResponse,
    HealthResponse,
    PaymentRequest,
    PaymentResponse,
    StatusResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

app = FastAPI(
    title="Finnet Integration API",
    version="1.0.0",
    description="Integração com Finnet Open Banking V1.2 para pagamento de tributos",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://butterfly.petlove.cloud"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        env=settings.env,
        finnet_base_url=settings.base_url,
    )


@app.post(
    "/payments/submit",
    response_model=PaymentResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def submit_payment(body: PaymentRequest):
    try:
        correlation_id = finnet.submit_payment(body.model_dump())
        return PaymentResponse(correlation_id=correlation_id)
    except FinnetAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except FinnetPaymentError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=str(exc),
        )


@app.get(
    "/payments/{correlation_id}/status",
    response_model=StatusResponse,
    responses={502: {"model": ErrorResponse}},
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
