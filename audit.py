import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

# Emite JSON estruturado — o Cloud Logging da GCP ingere automaticamente
_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_payment_request(
    *,
    caller: str,
    idempotency_key: str,
    barcode: str,
    amount: float,
    tribute_code: int,
    taxpayer_cnpj: str,
    env: str,
) -> None:
    _logger.info(json.dumps({
        "timestamp_utc": _now_utc(),
        "level": "INFO",
        "event": "payment_requested",
        "service": "api-impostos",
        "environment": env,
        "caller": caller,
        "idempotency_key": idempotency_key,
        "barcode": barcode,
        "amount": amount,
        "tribute_code": tribute_code,
        "taxpayer_cnpj": taxpayer_cnpj,
    }, ensure_ascii=False))


def log_payment_result(
    *,
    caller: str,
    idempotency_key: str,
    barcode: str,
    correlation_id: Optional[str],
    status: str,
    error: Optional[str] = None,
    env: str,
) -> None:
    _logger.info(json.dumps({
        "timestamp_utc": _now_utc(),
        "level": "INFO" if status == "SUCCESS" else "ERROR",
        "event": "payment_result",
        "service": "api-impostos",
        "environment": env,
        "caller": caller,
        "idempotency_key": idempotency_key,
        "barcode": barcode,
        "correlation_id": correlation_id,
        "status": status,
        "error": error,
    }, ensure_ascii=False))


def log_duplicate_blocked(
    *,
    caller: str,
    idempotency_key: str,
    env: str,
) -> None:
    _logger.info(json.dumps({
        "timestamp_utc": _now_utc(),
        "level": "WARNING",
        "event": "duplicate_blocked",
        "service": "api-impostos",
        "environment": env,
        "caller": caller,
        "idempotency_key": idempotency_key,
    }, ensure_ascii=False))
