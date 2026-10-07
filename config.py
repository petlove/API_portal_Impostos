import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ambiente: "homolog" ou "production"
    env: str = "homolog"

    # URLs base por ambiente
    homolog_base_url: str = "https://openbanking-homol.finnet.com.br"
    production_base_url: str = "https://openbanking.finnet.com.br"

    # Credenciais
    finnet_username: str = "Petlove.homol"
    finnet_password: str = ""  # definir no .env

    # Secret para geração do x-token-validate (HMAC-SHA256 do body)
    # Confirmar o valor exato com a Finnet — pode ser o token_callback do cadastro
    finnet_token_secret: str = ""

    # Dados bancários — Bradesco (banco 237)
    bank_identifier: int = 237
    bank_branch: int = 1        # Agência 001
    bank_branch_identifier: str = "0"
    bank_account: int = 117364011
    bank_account_identifier: str = "0"
    bank_agreement: str = "12345"

    # Dados da empresa pagadora (POC — dados fictícios fornecidos pela Finnet)
    company_registered_number: str = "20274100000113"
    company_name: str = "DOGHERO AGENCIA ONLINE DE SERVICOS"
    company_type: int = 2  # 2 = CNPJ / Pessoa Jurídica
    company_address_zip_code: int = 0
    company_address: str = ""
    company_address_number: int = 0
    company_address_complement: str = ""
    company_address_neighborhood: str = ""
    company_address_city: str = "São Paulo"
    company_address_state: str = "SP"

    @property
    def base_url(self) -> str:
        if self.env == "production":
            return self.production_base_url
        return self.homolog_base_url

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/v1-2/login"

    @property
    def refresh_url(self) -> str:
        return f"{self.base_url}/v1-2/login/refresh"

    @property
    def payment_url(self) -> str:
        return f"{self.base_url}/payment"

    @property
    def payment_status_url(self) -> str:
        return f"{self.base_url}/payment"

    @property
    def return_available_url(self) -> str:
        return f"{self.base_url}/return-available"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
