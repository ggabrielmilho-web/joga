"""Testes da cascata do DRE (dre_demo.calcular). Validam a estrutura contábil."""
import pytest
from operacoes import dre_demo


@pytest.fixture(scope='module')
def dre():
    return dre_demo.calcular(12)


def test_cascata_fecha(dre):
    # Receita Líquida = Receita Bruta - Deduções
    assert abs(dre['receita_liquida'] - (dre['receita_bruta'] - dre['Deduções'])) < 1
    # EBITDA = Receita Líquida - Custo Operacional - Despesas Administrativas
    eb = dre['receita_liquida'] - dre['Custo Operacional'] - dre['Despesas Administrativas']
    assert abs(dre['ebitda'] - eb) < 1
    # Resultado Final = EBITDA - Financeiras - Impostos - Investimentos - Retiradas
    rf = (dre['ebitda'] - dre['Despesas Financeiras'] - dre['Impostos']
          - dre['Investimentos'] - dre['Retiradas'])
    assert abs(dre['resultado_final'] - rf) < 1


def test_estrutura_14_linhas(dre):
    assert len(dre['estrutura']) == 14
    assert dre['estrutura'][0]['linha'] == 'Receita Bruta'
    assert dre['estrutura'][-1]['linha'] == '= Resultado Final'


def test_soma_eventos_igual_total_do_grupo(dre):
    for grupo, g in dre['grupos_drill'].items():
        soma = sum(ev['valor'] for sub in g['subgrupos'] for ev in sub['eventos'])
        assert abs(soma - g['total']) < 1, grupo


def test_custo_operacional_e_o_maior_grupo(dre):
    totais = {g: v['total'] for g, v in dre['grupos_drill'].items()}
    assert max(totais, key=totais.get) == 'Custo Operacional'


def test_resultado_final_positivo_e_realista(dre):
    # margem final entre 0 e 10% (transporte)
    assert 0 < dre['margem_final'] < 10


def test_serie_mensal_12_meses(dre):
    assert len(dre['serie']) == 12
    assert all('receita' in m and 'ebitda' in m and 'resultado' in m for m in dre['serie'])
