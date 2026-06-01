"""Autenticação por e-mail/senha com persistência.

- Em produção (DB_HOST setado) usa **Postgres**: cria o database (DB_NAME, default 'joga')
  e a tabela `joga_users`, com usuário admin semeado.
- Local (sem DB_HOST) cai em **SQLite** (data/demo.sqlite) — zero setup pra testar.

Idempotente: re-rodar não duplica usuários.
"""
import os
import time
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

import config

SENHA_PADRAO = 'admin123'

# Usuários semeados. O admin é o solicitado; os demais permitem demonstrar o RBAC
# (basta logar com o e-mail correspondente). Todos com a senha padrão admin123.
SEED_USERS = [
    # (nome, email, role, codusur, codsupervisor)
    ('Administrador JOGA',          'joga@adm.com.br',        'admin',      None, None),
    ('Supervisor — Equipe Capital', 'supervisor@joga.com.br', 'supervisor', None, 11),
    ('Vendedor — Carlos Nunes',     'vendedor@joga.com.br',   'vendedor',   107,  None),
    ('Visitante',                   'viewer@joga.com.br',     'viewer',     None, None),
]


def _is_pg():
    return bool(os.getenv('DB_HOST'))


def _app_db_name():
    return os.getenv('DB_NAME', 'joga')


def _pg_connect(dbname):
    import psycopg2
    return psycopg2.connect(
        host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT', '5432'),
        dbname=dbname, user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
    )


def _conn():
    """Conexão da aplicação + placeholder de parâmetro ('%s' pg / '?' sqlite)."""
    if _is_pg():
        return _pg_connect(_app_db_name()), '%s'
    c = sqlite3.connect(str(config.DEMO_SQLITE))
    c.row_factory = sqlite3.Row
    return c, '?'


def _ensure_database():
    """Postgres: cria o database (DB_NAME) se ainda não existir."""
    if not _is_pg():
        return
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    conn = _pg_connect('postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    dbn = _app_db_name()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbn,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{dbn}"')
        print(f"[init_auth] database '{dbn}' criado")
    cur.close()
    conn.close()


def init_auth(retries=20, delay=2):
    """Espera o banco subir, garante database + tabela + usuários. Idempotente."""
    ultimo = None
    for tentativa in range(retries):
        try:
            _ensure_database()
            conn, ph = _conn()
            cur = conn.cursor()
            if _is_pg():
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS joga_users (
                        id SERIAL PRIMARY KEY,
                        nome TEXT, email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'viewer', codusur INTEGER, codsupervisor INTEGER,
                        ativo BOOLEAN DEFAULT true, criado_em TIMESTAMP DEFAULT NOW()
                    )""")
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS joga_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT, email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'viewer', codusur INTEGER, codsupervisor INTEGER,
                        ativo INTEGER DEFAULT 1
                    )""")
            for nome, email, role, codusur, codsup in SEED_USERS:
                cur.execute(f"SELECT 1 FROM joga_users WHERE email = {ph}", (email,))
                if not cur.fetchone():
                    cur.execute(
                        f"INSERT INTO joga_users (nome, email, senha_hash, role, codusur, codsupervisor) "
                        f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                        (nome, email, generate_password_hash(SENHA_PADRAO), role, codusur, codsup))
            conn.commit()
            cur.close()
            conn.close()
            print(f"[init_auth] OK ({'postgres' if _is_pg() else 'sqlite'}) — {len(SEED_USERS)} usuários garantidos")
            return True
        except Exception as e:
            ultimo = e
            print(f"[init_auth] aguardando banco ({tentativa + 1}/{retries})... {e}")
            time.sleep(delay)
    print(f"[init_auth] FALHOU após {retries} tentativas: {ultimo}")
    return False


def autenticar(email, senha):
    """Valida e-mail/senha. Retorna dict de sessão ou None."""
    email = (email or '').strip().lower()
    try:
        conn, ph = _conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, nome, email, senha_hash, role, codusur, codsupervisor, ativo "
            f"FROM joga_users WHERE email = {ph}", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[autenticar] erro de banco: {e}")
        return None
    if not row:
        return None
    id_, nome, _em, senha_hash, role, codusur, codsup, ativo = (
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
    if not ativo:
        return None
    if not check_password_hash(senha_hash, senha or ''):
        return None
    return {
        'user_id': id_, 'nome': nome, 'role': role,
        'codusur': codusur, 'codsupervisor': codsup,
        'tipos_permitidos': ['receita', 'despesa', 'embarques', 'dre'],
    }
