from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Ambiente ──────────────────────────────────────────────────────────────
    env: str = "homolog"

    # ── URLs base ─────────────────────────────────────────────────────────────
    homolog_base_url: str = "https://openbanking-homol.finnet.com.br"
    production_base_url: str = "https://openbanking.finnet.com.br"

    # ── Autenticação da API (gerada pelo TI e configurada no Cloud Run) ────────
    api_key: str  # obrigatório — sem default; ausência levanta erro na inicialização

    # ── Credenciais Finnet — NUNCA colocar valores aqui; vêm do .env / Secret Manager
    finnet_username: str
    finnet_password: str
    finnet_token_secret: str = ""  # confirmar com suporte Finnet

    # ── Dados bancários ───────────────────────────────────────────────────────
    bank_identifier: int
    bank_branch: int
    bank_branch_identifier: str = "0"
    bank_account: int
    bank_account_identifier: str = "0"
    bank_agreement: str

    # ── Dados da empresa pagadora ─────────────────────────────────────────────
    company_registered_number: str
    company_name: str
    company_type: int = 2
    company_address_zip_code: int = 0
    company_address: str = ""
    company_address_number: int = 0
    company_address_complement: str = ""
    company_address_neighborhood: str = ""
    company_address_city: str = ""
    company_address_state: str = ""

    # ── CORS — origens permitidas (separadas por vírgula no .env) ────────────
    cors_origins: str = "https://butterfly.petlove.cloud"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def base_url(self) -> str:
        return self.production_base_url if self.env == "production" else self.homolog_base_url

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
