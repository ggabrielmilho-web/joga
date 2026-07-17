"""Testes do módulo puro do Radar de Produtos."""
from datetime import date, timedelta

from comercial import radar

HOJE = date(2026, 7, 17)


def _iso(dias_atras):
    return (HOJE - timedelta(days=dias_atras)).isoformat()


PRODUTOS = {
    '5000': {'codprod': 5000, 'descricao': 'Detergente Max 1L', 'codepto': 1,
             'codfornec': 200, 'fornec_nome': 'Bril Higiene SA', 'depto_nome': 'Material de Limpeza'},
    '5001': {'codprod': 5001, 'descricao': 'Sabão Gold 2kg', 'codepto': 1,
             'codfornec': 200, 'fornec_nome': 'Bril Higiene SA', 'depto_nome': 'Material de Limpeza'},
    '5100': {'codprod': 5100, 'descricao': 'Arroz Real 5kg', 'codepto': 2,
             'codfornec': 201, 'fornec_nome': 'Predileta Alimentos', 'depto_nome': 'Alimentícios'},
}

# c1: parou o 5000 (só comprou na janela anterior) mas comprou 5001 do mesmo depto agora → trocou
# c2: parou o 5000 e não comprou nada do depto → abandonou
# c3: segue comprando o 5000 (ativo)
CLIENTES = [
    {'codcli': 1, 'cliente': 'Cliente Um', 'cidade': 'Uberlândia', 'uf': 'MG',
     'vendedor': 'Ana', 'codusur': 100, 'telefone': '',
     'produtos': {'5000': [[_iso(90), 500.0, 5]], '5001': [[_iso(10), 400.0, 4]]}},
    {'codcli': 2, 'cliente': 'Cliente Dois', 'cidade': 'Uberaba', 'uf': 'MG',
     'vendedor': 'Ana', 'codusur': 100, 'telefone': '',
     'produtos': {'5000': [[_iso(80), 300.0, 3]]}},
    {'codcli': 3, 'cliente': 'Cliente Três', 'cidade': 'Goiânia', 'uf': 'GO',
     'vendedor': 'Bruno', 'codusur': 101, 'telefone': '',
     'produtos': {'5000': [[_iso(100), 200.0, 2], [_iso(5), 250.0, 2]],
                  '5100': [[_iso(3), 900.0, 9]]}},
]


def test_status_classificacao():
    assert radar.status(None, 0, 0, 60) == 'perdido'
    assert radar.status(130, 0, 100, 60) == 'perdido'   # ≥ 2×dias
    assert radar.status(70, 0, 100, 60) == 'parou'      # ≥ dias
    assert radar.status(10, 20, 100, 60) == 'esfriando'  # caiu > 50%
    assert radar.status(10, 90, 100, 60) == 'ativo'


def test_board_so_mostra_quem_sangra_e_ordena_por_queda():
    rows = radar.board(CLIENTES, PRODUTOS, 60, HOJE)
    quedas = [r['queda_receita'] for r in rows]
    assert quedas == sorted(quedas, reverse=True)
    assert all(r['queda_receita'] > 0 for r in rows)
    # 5000 · janela 60d: recente = 250 (c3 @5d)
    #                    anterior [60,120) = c1 500 @90d + c2 300 @80d + c3 200 @100d = 1000
    p5000 = next(r for r in rows if r['codprod'] == 5000)
    assert p5000['venda_rec'] == 250.0
    assert p5000['venda_ant'] == 1000.0
    assert p5000['queda_receita'] == 750.0
    assert p5000['pct_queda'] == 0.75
    assert p5000['clientes_perdidos'] == 2   # 3 clientes antes (c1,c2,c3), 1 agora (c3)


def test_board_ignora_produto_que_cresceu():
    rows = radar.board(CLIENTES, PRODUTOS, 60, HOJE)
    # 5001 e 5100 só têm venda na janela recente → não sangram
    assert {r['codprod'] for r in rows} == {5000}


def test_detalhe_troca_vs_abandono():
    info, linhas = radar.detalhe(CLIENTES, PRODUTOS, 5000, 60, HOJE)
    assert info['descricao'] == 'Detergente Max 1L'
    por_cli = {l['codcli']: l for l in linhas}
    # c1 parou o 5000 mas comprou 5001 (mesmo depto) na janela recente → trocou
    assert por_cli[1]['status'] in ('parou', 'perdido')
    assert por_cli[1]['trocou'] is True
    # c2 parou e não comprou nada do depto → abandonou
    assert por_cli[2]['status'] in ('parou', 'perdido')
    assert por_cli[2]['trocou'] is False
    # c3 comprou há 5 dias → ativo
    assert por_cli[3]['status'] == 'ativo'


def test_detalhe_so_clientes_do_produto():
    _info, linhas = radar.detalhe(CLIENTES, PRODUTOS, 5100, 60, HOJE)
    assert [l['codcli'] for l in linhas] == [3]   # só o c3 comprou o 5100


def test_detalhe_ordena_por_venda_12m():
    _info, linhas = radar.detalhe(CLIENTES, PRODUTOS, 5000, 60, HOJE)
    vendas = [l['venda_12m'] for l in linhas]
    assert vendas == sorted(vendas, reverse=True)
