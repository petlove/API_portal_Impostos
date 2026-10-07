from __future__ import annotations

import hmac
import hashlib
import json
import time
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Margem de segurança: renova o token 10 minutos antes de expirar
_RENEW_MARGIN_SECONDS = 600


class FinnetAuthError(Exception):
    pass


class FinnetPaymentError(Exception):
    def __init__(self, message: str, status_code: int = None, body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


# ---------------------------------------------------------------------------
# Token de validação por assinatura (x-token-validate)
# A Finnet exige um HMAC-SHA256 do corpo da requisição usando o token_secret.
# Confirmar o valor exato de FINNET_TOKEN_SECRET com o suporte da Finnet.
# ---------------------------------------------------------------------------
def _generate_x_token_validate(body_dict: dict) -> str:
    if not settings.finnet_token_secret:
        # POC: retorna string vazia se o secret não estiver configurado.
        # Em produção o header é obrigatório — a chamada pode ser rejeitada.
        logger.warning("FINNET_TOKEN_SECRET não configurado — x-token-validate enviado vazio")
        return ""
    body_json = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
    signature = hmac.new(
        settings.finnet_token_secret.encode("utf-8"),
        body_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------
class FinnetClient:
    def __init__(self):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._access_expires_at: float = 0
        self._refresh_expires_at: float = 0
        self._http = httpx.Client(timeout=30)

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    def _store_tokens(self, data: dict) -> None:
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        expires_token = data.get("expires_token", 360)      # minutos
        expires_refresh = data.get("expires_refresh_token", 720)

        now = time.time()
        self._access_expires_at = now + (expires_token * 60) - _RENEW_MARGIN_SECONDS
        self._refresh_expires_at = now + (expires_refresh * 60) - _RENEW_MARGIN_SECONDS

        logger.info(
            "Tokens armazenados. access expira em %d min, refresh em %d min",
            expires_token, expires_refresh,
        )

    def _access_valid(self) -> bool:
        return self._access_token is not None and time.time() < self._access_expires_at

    def _refresh_valid(self) -> bool:
        return self._refresh_token is not None and time.time() < self._refresh_expires_at

    def _do_login(self) -> None:
        logger.info("Autenticando na Finnet (%s)...", settings.env)
        resp = self._http.post(
            settings.login_url,
            json={"username": settings.finnet_username, "password": settings.finnet_password},
        )
        if resp.status_code != 200:
            raise FinnetAuthError(
                f"Login falhou: HTTP {resp.status_code} — {resp.text[:200]}"
            )
        self._store_tokens(resp.json())

    def _do_refresh(self) -> None:
        logger.info("Renovando access_token via refresh_token...")
        resp = self._http.post(
            settings.refresh_url,
            json={"refresh_token": self._refresh_token},
        )
        if resp.status_code != 200:
            logger.warning("Refresh falhou (%s) — fazendo login completo", resp.status_code)
            self._do_login()
            return
        self._store_tokens(resp.json())

    def authenticate(self) -> str:
        """Retorna um access_token válido, renovando se necessário."""
        if self._access_valid():
            return self._access_token
        if self._refresh_valid():
            self._do_refresh()
        else:
            self._do_login()
        return self._access_token

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------

    def _company_payload(self) -> dict:
        return {
            "bank_identifier": settings.bank_identifier,
            "bank_branch": settings.bank_branch,
            "bank_branch_identifier": settings.bank_branch_identifier,
            "bank_account": settings.bank_account,
            "bank_account_identifier": settings.bank_account_identifier,
            "bank_agreement": settings.bank_agreement,
            "registered_number": settings.company_registered_number,
            "type": settings.company_type,
            "name": settings.company_name,
            "address_zip_code": settings.company_address_zip_code,
            "address": settings.company_address,
            "address_number": settings.company_address_number,
            "address_complement": settings.company_address_complement,
            "address_neighborhood": settings.company_address_neighborhood,
            "address_city": settings.company_address_city,
            "address_state": settings.company_address_state,
        }

    @staticmethod
    def _tribute_payment_payload(data: dict) -> dict:
        """
        Monta o TributePaymentSchema para pagamento de impostos.
        Códigos de tributo (Bradesco 240):
          16 = DARF Normal | 17 = GPS | 18 = DARF Simples | 19 = IPTU
          21 = DARJ | 22 = GARE-SP ICMS | 23 = GARE-SP DR | 24 = GARE-SP ITCMD
          25 = IPVA | 26 = Licenciamento | 27 = DPVAT
        """
        payload = {
            "transaction_type": 0,    # 0 = Inclusão
            "transaction_code": "00", # 00 = Inclusão liberada
            "tribute_code": data["tribute_code"],
            "barcode": data["barcode"],
            "due_date": data["due_date"],
            "payment_date": data["payment_date"],
            "amount": data["amount"],
            "taxpayer": {
                "type": 2,            # 2 = CNPJ
                "registered_number": data["taxpayer_cnpj"],
            },
        }
        if data.get("fine_amount"):
            payload["fine_amount"] = data["fine_amount"]
        if data.get("interest_amount"):
            payload["interest_amount"] = data["interest_amount"]
        return payload

    def _auth_headers(self, body: dict) -> dict:
        token = self.authenticate()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-token-validate": _generate_x_token_validate(body),
        }

    # ------------------------------------------------------------------
    # Envio de pagamento
    # ------------------------------------------------------------------

    def submit_payment(self, payment_data: dict) -> str:
        """Envia um pagamento de tributo. Retorna o correlation_id."""
        body = {
            "company": self._company_payload(),
            "payments": [self._tribute_payment_payload(payment_data)],
        }
        headers = self._auth_headers(body)

        resp = self._http.post(settings.payment_url, json=body, headers=headers)

        # Token expirou inesperadamente — reautentica e retenta uma vez
        if resp.status_code == 403:
            logger.warning("403 em submit_payment — reautenticando e retentando")
            self._access_token = None
            headers = self._auth_headers(body)
            resp = self._http.post(settings.payment_url, json=body, headers=headers)

        if resp.status_code != 200:
            raise FinnetPaymentError(
                f"Erro ao enviar pagamento: HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=resp.json() if resp.content else {},
            )

        data = resp.json()
        correlation_id = data.get("correlation_id")
        if not correlation_id:
            raise FinnetPaymentError("correlation_id ausente na resposta da Finnet")

        logger.info("Pagamento enviado com sucesso. correlation_id=%s", correlation_id)
        return correlation_id

    # ------------------------------------------------------------------
    # Consulta de status
    # ------------------------------------------------------------------

    def get_payment_status(self, correlation_id: str) -> dict:
        """Consulta o status de um pagamento pelo correlation_id."""
        token = self.authenticate()
        url = f"{settings.payment_status_url}/{correlation_id}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"_offset": 0, "_limit": 10}

        resp = self._http.get(url, headers=headers, params=params)

        if resp.status_code == 403:
            logger.warning("403 em get_payment_status — reautenticando")
            self._access_token = None
            token = self.authenticate()
            headers["Authorization"] = f"Bearer {token}"
            resp = self._http.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            raise FinnetPaymentError(
                f"Erro ao consultar status: HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=resp.json() if resp.content else {},
            )

        data = resp.json()
        results = data.get("results", [])
        first = results[0] if results else {}
        return {
            "status": first.get("status", "DESCONHECIDO"),
            "reject_reason": first.get("reject_reason"),
            "raw": data,
        }

    # ------------------------------------------------------------------
    # Return Available (POC hook — consumo futuro do retorno bancário)
    # ------------------------------------------------------------------

    def get_return_available(self, from_date: str, to_date: str, page: int = 1, status: str = None) -> dict:
        """
        Consulta retornos disponíveis na Finnet.
        Preparado para uso futuro quando o relacionamento direto com o banco for estabelecido.
        from_date / to_date: formato YYYY-MM-DD
        status: 'CREATED' | 'REJECTED' | 'DELIVERED' (opcional)
        """
        token = self.authenticate()
        params = {"fromDate": from_date, "toDate": to_date, "page": page}
        if status:
            params["status"] = status

        resp = self._http.get(
            settings.return_available_url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )

        if resp.status_code != 200:
            raise FinnetPaymentError(
                f"Erro ao consultar return-available: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        return resp.json()

    def close(self):
        self._http.close()


# Singleton — token em cache entre requisições
finnet = FinnetClient()
