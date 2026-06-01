"""Conexão de banco do módulo Operações (logística).

Operações usa SEMPRE SQLite (data/demo.sqlite, embutido na imagem no build).
A autenticação é separada e fica em shared/auth_db.py (Postgres em produção).
Manter SQLite aqui evita que o DB_HOST (usado pela auth) quebre as queries
de cargas/DRE, que vivem no SQLite.
"""
import sqlite3
import config


def get_db():
    conn = sqlite3.connect(str(config.DEMO_SQLITE))
    conn.row_factory = sqlite3.Row
    return conn
