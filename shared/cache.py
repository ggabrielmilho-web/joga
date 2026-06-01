"""Cache em memória com TTL, interface compatível com o uso do Multpel.

Sem dependência de Redis. Mantém as assinaturas _cache_get / _cache_set
para reaproveitar a lógica dos endpoints originais. Em demo, um dict basta
(processo único) e ainda evita recomputar agregações pesadas.
"""
import time
import json
from flask import session

_STORE = {}  # {key: (expira_em_epoch, valor)}

_CACHE_TTLS = {
    'dax_agregado': 3600,
    'dax_lista':     300,
    'metadata':    86400,
    'token_pbi':    3000,
}


def _cache_get(key):
    item = _STORE.get(key)
    if not item:
        return None
    expira, valor = item
    if expira < time.time():
        _STORE.pop(key, None)
        return None
    return valor


def _cache_set(key, data, ttl_tipo='dax_agregado'):
    ttl = _CACHE_TTLS.get(ttl_tipo, 3600)
    # round-trip por JSON pra imitar o comportamento do Redis (cópia, datas viram str)
    serial = json.loads(json.dumps(data, default=str))
    _STORE[key] = (time.time() + ttl, serial)


def cache_key_for_user(endpoint, params=None):
    """Chave inclui o escopo RBAC do usuário logado (evita vazar entre papéis)."""
    parts = [
        'joga', endpoint,
        f"role={session.get('role', 'anon')}",
        f"usur={session.get('codusur', '-')}",
        f"supv={session.get('codsupervisor', '-')}",
    ]
    if params:
        parts.append(json.dumps(params, sort_keys=True))
    return ':'.join(parts)


def limpar_cache():
    _STORE.clear()
