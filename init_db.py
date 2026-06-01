"""Inicialização do banco de autenticação (rodado no start do container).

Cria o database (DB_NAME, default 'joga'), a tabela joga_users e o admin.
Idempotente. Espera o Postgres subir (retry).
"""
from shared.auth_db import init_auth

if __name__ == '__main__':
    init_auth()
