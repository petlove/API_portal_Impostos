import hashlib
import time
from typing import Optional

# TTL de 24 horas — cobre reenvios acidentais no mesmo dia fiscal
_TTL_SECONDS = 86_400

# { idempotency_key: {"correlation_id": str, "expires_at": float} }
_store: dict = {}


def _purge_expired() -> None:
    now = time.time()
    expired = [k for k, v in _store.items() if v["expires_at"] < now]
    for k in expired:
        del _store[k]


def make_key(barcode: str, amount: float, due_date: str) -> str:
    """
    Gera uma chave determinística a partir dos dados da guia.
    Pode ser usada quando o portal não envia um Idempotency-Key explícito.
    """
    raw = f"{barcode}|{amount:.2f}|{due_date}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str) -> Optional[str]:
    """Retorna o correlation_id se a chave já foi processada, None caso contrário."""
    _purge_expired()
    entry = _store.get(key)
    if entry and entry["expires_at"] > time.time():
        return entry["correlation_id"]
    return None


def register(key: str, correlation_id: str) -> None:
    """Registra uma chave como processada com sucesso."""
    _store[key] = {
        "correlation_id": correlation_id,
        "expires_at": time.time() + _TTL_SECONDS,
    }
