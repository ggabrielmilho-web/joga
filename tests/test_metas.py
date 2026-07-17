"""Testes do módulo puro de Metas."""
from comercial import metas


def test_projecao_run_rate():
    # metade dos dias úteis decorridos → projeção = 2× o realizado
    assert metas.projecao(100, 20, 10) == 200
    # sem dia decorrido → não extrapola
    assert metas.projecao(100, 20, 0) == 100


def test_falta_nunca_negativa():
    assert metas.falta(100, 30) == 70
    assert metas.falta(100, 150) == 0.0


def test_necessidade_dia():
    assert metas.necessidade_dia(100, 40, 6) == 10.0
    # mês encerrado
    assert metas.necessidade_dia(100, 40, 0) == 0.0


def test_pct_seguro():
    assert metas.pct(50, 100) == 0.5
    assert metas.pct(50, 0) is None


def test_linha_metrica_completa():
    l = metas.linha_metrica(1000, 400, 20, 10, 10)
    assert l['meta'] == 1000 and l['realizado'] == 400
    assert l['falta'] == 600
    assert l['projecao'] == 800            # run-rate 400×20/10
    assert l['pct_realizado'] == 0.4
    assert round(l['pct_projecao'], 3) == 0.8
    assert l['necessidade_dia'] == 60.0    # 600/10


def test_somar_aditivo():
    linhas = [{'realizado': 10}, {'realizado': 20}, {'realizado': 5}]
    assert metas.somar_aditivo(linhas, 'realizado') == 35


def test_clientes_mix_nao_sao_somados_em_rollup():
    # clientes/mix são DISTINCTCOUNT — o módulo nunca oferece soma automática deles;
    # só venda/rentabilidade estão na lista de métricas aditivas.
    assert 'clientes' not in metas.METRICAS_ADITIVAS
    assert 'mix' not in metas.METRICAS_ADITIVAS
    assert set(metas.METRICAS_ADITIVAS) == {'venda', 'rentabilidade'}


def test_sugerir_ano_anterior():
    hist = {202507: 50000.0}
    assert metas.sugerir(hist, 2026, 7, 'ano_anterior', 0.10) == 55000.0
    assert metas.sugerir({}, 2026, 7, 'ano_anterior') is None
