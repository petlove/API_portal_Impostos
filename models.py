from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, Field


class TributeCode(IntEnum):
    DARF_NORMAL = 16
    GPS = 17
    DARF_SIMPLES = 18
    IPTU = 19
    DARJ = 21
    GARE_SP_ICMS = 22
    GARE_SP_DR = 23
    GARE_SP_ITCMD = 24
    IPVA = 25
    LICENCIAMENTO = 26
    DPVAT = 27


class PaymentRequest(BaseModel):
    tribute_code: TributeCode = Field(..., description="Código do tributo (16-27)")
    barcode: str = Field(..., description="Código de barras ou linha digitável")
    due_date: str = Field(..., description="Data de vencimento (YYYY-MM-DD)")
    payment_date: str = Field(..., description="Data do pagamento (YYYY-MM-DD)")
    amount: float = Field(..., gt=0, description="Valor em reais (ex: 1500.00)")
    taxpayer_cnpj: str = Field(..., description="CNPJ do contribuinte (sem formatação)")
    fine_amount: Optional[float] = Field(None, description="Multa, se aplicável")
    interest_amount: Optional[float] = Field(None, description="Juros, se aplicável")


class PaymentResponse(BaseModel):
    correlation_id: str
    message: str = "Pagamento enviado para processamento"


class StatusResponse(BaseModel):
    correlation_id: str
    status: str
    reject_reason: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    finnet_status_code: Optional[int] = None
    finnet_body: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    env: str
    finnet_base_url: str
