"""
Script de teste rápido: valida autenticação na Finnet (homologação).
Execute: python test_connection.py
"""
import httpx
from config import settings

print(f"Ambiente : {settings.env}")
print(f"Endpoint : {settings.login_url}")
print(f"Usuário  : {settings.finnet_username}")
print()

payload = {"username": settings.finnet_username, "password": settings.finnet_password}

try:
    resp = httpx.post(settings.login_url, json=payload, timeout=15)
    print(f"HTTP Status: {resp.status_code}")
    data = resp.json()

    if resp.status_code == 200:
        token = data.get("access_token", "")
        print(f"access_token  : {token[:40]}...")
        print(f"refresh_token : {str(data.get('refresh_token', ''))[:40]}...")
        print(f"expires_token : {data.get('expires_token')} min")
        print()
        print("AUTENTICACAO OK — Finnet homolog acessivel!")
    else:
        print(f"ERRO: {data}")

except httpx.ConnectError as exc:
    print(f"Falha de conexao: {exc}")
except Exception as exc:
    print(f"Erro inesperado: {exc}")
