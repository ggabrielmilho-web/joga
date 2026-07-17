"""Smoke + RBAC do app JOGA. Garante que as telas e APIs respondem e que
o controle de acesso por papel não vaza dados entre perfis."""
import pytest
from app import app as flask_app
from shared.auth_db import init_auth

# garante a tabela joga_users + usuários semeados (SQLite local em teste)
init_auth()

EMAILS = {
    'diretor':    'joga@adm.com.br',
    'supervisor': 'supervisor@joga.com.br',
    'vendedor':   'vendedor@joga.com.br',
    'viewer':     'viewer@joga.com.br',
}


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    return flask_app.test_client()


def login(client, papel):
    return client.post('/login', json={'email': EMAILS[papel], 'senha': 'admin123'})


PAGINAS = [
    '/', '/comercial/', '/comercial/carteira', '/comercial/vendedores',
    '/comercial/categorias', '/comercial/mix', '/comercial/tendencias',
    '/comercial/gerencial', '/comercial/radar', '/comercial/metas',
    '/operacoes/', '/operacoes/dre', '/operacoes/embarques', '/operacoes/mapa',
]
APIS = [
    '/comercial/api/dashboard/kpis', '/comercial/api/carteira/rfm',
    '/comercial/api/carteira/clientes?limit=5', '/comercial/api/vendedores',
    '/comercial/api/tendencias/cohort', '/comercial/api/categorias',
    '/comercial/api/gerencial/cobertura', '/comercial/api/radar/board?dias=60',
    '/comercial/api/radar/fornecedores', '/comercial/api/metas',
    '/comercial/api/metas/serie',
    '/operacoes/api/dre', '/operacoes/api/embarques/kpis',
    '/operacoes/api/rastreamento/posicoes',
]


def test_login_invalido(client):
    r = client.post('/login', json={'email': 'naoexiste@x.com', 'senha': 'errada'})
    assert r.status_code == 401


@pytest.mark.parametrize('url', PAGINAS)
def test_paginas_diretor(client, url):
    login(client, 'diretor')
    r = client.get(url, follow_redirects=True)
    assert r.status_code == 200


@pytest.mark.parametrize('url', APIS)
def test_apis_diretor(client, url):
    login(client, 'diretor')
    r = client.get(url)
    assert r.status_code == 200
    assert r.get_json().get('ok') is True


def test_sem_login_redireciona(client):
    r = client.get('/comercial/')
    assert r.status_code in (302, 308)


def test_rbac_vendedor_sem_ranking(client):
    login(client, 'vendedor')
    assert client.get('/comercial/api/vendedores').status_code == 403
    assert client.get('/comercial/api/vendedor/107').status_code == 200
    assert client.get('/comercial/api/vendedor/100').status_code == 403


def test_rbac_escopo_carteira(client):
    login(client, 'diretor')
    tot_d = client.get('/comercial/api/carteira/clientes?limit=1').get_json()['total']
    login(client, 'supervisor')
    tot_s = client.get('/comercial/api/carteira/clientes?limit=1').get_json()['total']
    login(client, 'vendedor')
    tot_v = client.get('/comercial/api/carteira/clientes?limit=1').get_json()['total']
    assert tot_d > tot_s > tot_v > 0


def test_supervisor_nao_ve_vendedor_de_outro_time(client):
    login(client, 'supervisor')
    assert client.get('/comercial/api/vendedor/100').status_code == 403


def test_gerencial_escopo_por_papel(client):
    login(client, 'diretor')
    td = client.get('/comercial/api/gerencial/cobertura').get_json()['empresa']['total_clientes']
    login(client, 'supervisor')
    ts = client.get('/comercial/api/gerencial/cobertura').get_json()['empresa']['total_clientes']
    login(client, 'vendedor')
    tv = client.get('/comercial/api/gerencial/cobertura').get_json()['empresa']['total_clientes']
    assert td > ts > tv > 0


def test_metas_drill_rbac(client):
    login(client, 'diretor')
    p = client.get('/comercial/api/metas').get_json()
    assert p['ok'] and p['times']
    algum = p['times'][0]['codsupervisor']
    assert client.get(f'/comercial/api/metas/vendedores?codsupervisor={algum}').status_code == 200
    # vendedor (time 11) tentando drill de OUTRO time → 403
    login(client, 'vendedor')
    assert client.get('/comercial/api/metas/vendedores?codsupervisor=10').status_code == 403


def test_radar_drill_produto(client):
    login(client, 'diretor')
    board = client.get('/comercial/api/radar/board?dias=60').get_json()
    assert board['ok'] and board['rows']
    cp = board['rows'][0]['codprod']
    d = client.get(f'/comercial/api/radar/produto/{cp}?dias=60').get_json()
    assert d['ok'] and d['produto']['codprod'] == cp
