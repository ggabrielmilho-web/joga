"""Conexão de banco para o módulo Operações (logística).

Padrão: SQLite local (data/demo.sqlite) — zero infra para validar local.
Se DB_HOST estiver setado, usa Postgres (caminho de produção/compose).

Em demo, só a logística usa banco; o comercial é 100% JSON sintético.
"""
import os
import sqlite3
import config


def usando_postgres():
    return bool(os.getenv('DB_HOST'))


def get_db():
    if usando_postgres():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            dbname=os.getenv('DB_NAME', 'joga_demo'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
        )
        return conn
    # SQLite: row_factory pra acessar por nome de coluna como no dict cursor
    conn = sqlite3.connect(str(config.DEMO_SQLITE))
    conn.row_factory = sqlite3.Row
    return conn
