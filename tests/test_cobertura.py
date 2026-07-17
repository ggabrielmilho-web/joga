"""Testes do motor puro de Cobertura (Gerencial)."""
from comercial import cobertura


def _cli(recencia, venda, status='ok', sup=10, usur=100, risco=0.0):
    return {'recencia_dias': recencia, 'venda_12m': venda, 'status_personalizada': status,
            'receita_perdida_proj': risco, 'codsupervisor': sup, 'time': f'Time {sup}',
            'codusur': usur, 'vendedor': f'V{usur}'}


BASE = [
    _cli(5, 1000, 'ok', 10, 100), _cli(20, 2000, 'normal', 10, 101),
    _cli(40, 1500, 'atencao', 11, 105), _cli(200, 800, 'urgente', 11, 106, risco=300),
    _cli(10, 3000, 'ok', 11, 106),
]


def test_faixa_de():
    assert cobertura.faixa_de(0) == '0-15'
    assert cobertura.faixa_de(30) == '16-30'
    assert cobertura.faixa_de(500) == '91+'
    assert cobertura.faixa_de(None) == '91+'
    assert cobertura.faixa_de(-3) == '91+'


def test_faixas_somam_o_total():
    g = cobertura.agregar_grupo(BASE, coberto_dias=30)
    assert sum(b['clientes'] for b in g['buckets']) == len(BASE)
    assert g['total_clientes'] == len(BASE)


def test_cobertura_entre_0_e_1():
    g = cobertura.agregar_grupo(BASE, coberto_dias=30)
    assert 0.0 <= g['cobertura_clientes'] <= 1.0
    assert 0.0 <= g['cobertura_valor'] <= 1.0
    # 3 clientes com recência ≤ 30 (5, 20, 10)
    assert g['clientes_cobertos'] == 3


def test_empresa_reconcilia_com_times():
    niveis = cobertura.agregar_niveis(BASE, coberto_dias=30)
    soma_times = sum(t['total_clientes'] for t in niveis['times'])
    soma_vend = sum(v['total_clientes'] for v in niveis['vendedores'])
    assert soma_times == niveis['empresa']['total_clientes']
    assert soma_vend == niveis['empresa']['total_clientes']


def test_ordenacao_pior_para_melhor():
    niveis = cobertura.agregar_niveis(BASE, coberto_dias=30)
    cobs = [t['cobertura_clientes'] for t in niveis['times']]
    assert cobs == sorted(cobs)


def test_alerta_abaixo_do_limiar():
    # time 10 = 2/2 coberto (100%); time 11 = 1/3 (33%)
    niveis = cobertura.agregar_niveis(BASE, coberto_dias=30)
    assert [t['id'] for t in cobertura.times_rcas_abaixo(niveis, 50)['times']] == [11]
    # quem está exatamente NO limiar não conta como abaixo
    assert [t['id'] for t in cobertura.times_rcas_abaixo(niveis, 100)['times']] == [11]
    # limiar 0 → ninguém abaixo
    assert cobertura.times_rcas_abaixo(niveis, 0)['times'] == []
