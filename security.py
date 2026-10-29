import secrets

from fastapi import Header, HTTPException, status

from config import settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Dependency do FastAPI: valida o header X-API-Key em todas as rotas protegidas.
    Usa comparação em tempo constante (secrets.compare_digest) para evitar timing attacks.
    """
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida ou ausente.",
        )
    return x_api_key
