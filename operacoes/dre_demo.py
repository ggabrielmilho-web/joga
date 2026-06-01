"""Cálculo do DRE em cascata (estrutura contábil obrigatória).

Espelha a estrutura do DRE original (Tabela Auditoria: DRE_LINHAS / _calcular_dre_periodo):
  Receita Bruta → (-) Deduções → = Receita Líquida → (-) Custo Operacional
  → (-) Despesas Administrativas → = EBITDA → (-) Despesas Financeiras → = LAIR
  → (-) Impostos → = Lucro Líquido → (-) Investimentos → = Pós-Investimento
  → (-) Retiradas → = Resultado Final

Função pura sobre as linhas de `dre_mensal`. Testável em tests/test_dre.py.
"""
from collections import defaultdict
from . import data

# Grupos de despesa na ordem em que entram na cascata
GRUPOS_DESPESA = [
    'Deduções', 'Custo Operacional', 'Despesas Administrativas',
    'Despesas Financeiras', 'Impostos', 'Investimentos', 'Retiradas',
]

# Cascata: (rótulo, tipo, chave). tipo 'grupo' = linha subtraível; 'subtotal' = acumulado.
DRE_LINHAS = [
    ('Receita Bruta',                 'subtotal', 'receita_bruta'),
    ('(-) Deduções',                  'grupo',    'Deduções'),
    ('= Receita Líquida',             'subtotal', 'receita_liquida'),
    ('(-) Custo Operacional',         'grupo',    'Custo Operacional'),
    ('(-) Despesas Administrativas',  'grupo',    'Despesas Administrativas'),
    ('= EBITDA',                      'subtotal', 'ebitda'),
    ('(-) Despesas Financeiras',      'grupo',    'Despesas Financeiras'),
    ('= LAIR',                        'subtotal', 'lair'),
    ('(-) Impostos',                  'grupo',    'Impostos'),
    ('= Lucro Líquido',               'subtotal', 'lucro_liquido'),
    ('(-) Investimentos',             'grupo',    'Investimentos'),
    ('= Pós-Investimento',            'subtotal', 'pos_investimento'),
    ('(-) Retiradas',                 'grupo',    'Retiradas'),
    ('= Resultado Final',             'subtotal', 'resultado_final'),
]


def calcular(meses=None):
    linhas = data.dre_mensal()
    todos_meses = sorted({l['anomes'] for l in linhas})
    if meses:
        todos_meses = todos_meses[-meses:]
    sel = set(todos_meses)

    receita = 0.0
    grupos = {g: 0.0 for g in GRUPOS_DESPESA}
    # drill: grupo → subgrupo → evento → valor
    drill = {g: defaultdict(lambda: defaultdict(float)) for g in GRUPOS_DESPESA}
    serie = defaultdict(lambda: {'receita': 0.0, 'despesa_op': 0.0, 'ebitda': 0.0, 'resultado': 0.0})

    for l in linhas:
        if l['anomes'] not in sel:
            continue
        if l['tipo'] == 'receita':
            receita += l['valor']
            serie[l['anomes']]['receita'] += l['valor']
        else:
            g = l['grupo']
            if g not in grupos:
                continue
            grupos[g] += l['valor']
            drill[g][l['subgrupo']][l['evento']] += l['valor']

    # subtotais da cascata
    receita_liquida  = receita - grupos['Deduções']
    ebitda           = receita_liquida - grupos['Custo Operacional'] - grupos['Despesas Administrativas']
    lair             = ebitda - grupos['Despesas Financeiras']
    lucro_liquido    = lair - grupos['Impostos']
    pos_investimento = lucro_liquido - grupos['Investimentos']
    resultado_final  = pos_investimento - grupos['Retiradas']

    valores = {
        'receita_bruta': receita,
        'receita_liquida': receita_liquida,
        'ebitda': ebitda,
        'lair': lair,
        'lucro_liquido': lucro_liquido,
        'pos_investimento': pos_investimento,
        'resultado_final': resultado_final,
        **grupos,
    }

    def pct(v):
        return round(v / receita * 100, 1) if receita else 0.0

    estrutura = []
    for rotulo, tipo, chave in DRE_LINHAS:
        v = valores[chave]
        estrutura.append({
            'linha': rotulo, 'tipo': tipo, 'chave': chave,
            'valor': round(v, 2), 'pct': pct(v),
        })

    # estrutura de drill por grupo
    grupos_drill = {}
    for g in GRUPOS_DESPESA:
        subs = []
        for sub, eventos in drill[g].items():
            total_sub = sum(eventos.values())
            subs.append({
                'subgrupo': sub, 'total': round(total_sub, 2), 'pct': pct(total_sub),
                'eventos': sorted(
                    ({'evento': e, 'valor': round(val, 2), 'pct': pct(val)}
                     for e, val in eventos.items()), key=lambda x: -x['valor']),
            })
        subs.sort(key=lambda x: -x['total'])
        grupos_drill[g] = {'total': round(grupos[g], 2), 'pct': pct(grupos[g]), 'subgrupos': subs}

    # série mensal (receita / EBITDA / resultado) — recomputa EBITDA e resultado por mês
    serie_mensal = []
    por_mes_grupo = defaultdict(lambda: defaultdict(float))
    rec_mes = defaultdict(float)
    for l in linhas:
        if l['anomes'] not in sel:
            continue
        if l['tipo'] == 'receita':
            rec_mes[l['anomes']] += l['valor']
        elif l['grupo'] in grupos:
            por_mes_grupo[l['anomes']][l['grupo']] += l['valor']
    for am in todos_meses:
        r = rec_mes[am]
        gp = por_mes_grupo[am]
        eb = r - gp['Deduções'] - gp['Custo Operacional'] - gp['Despesas Administrativas']
        res = eb - gp['Despesas Financeiras'] - gp['Impostos'] - gp['Investimentos'] - gp['Retiradas']
        serie_mensal.append({'anomes': am, 'receita': round(r, 2),
                             'ebitda': round(eb, 2), 'resultado': round(res, 2)})

    return {
        'ok': True,
        'meses': todos_meses,
        'receita_bruta': round(receita, 2),
        'receita_liquida': round(receita_liquida, 2),
        'ebitda': round(ebitda, 2),
        'ebitda_margem': pct(ebitda),
        'lucro_liquido': round(lucro_liquido, 2),
        'resultado_final': round(resultado_final, 2),
        'margem_liquida': pct(lucro_liquido),
        'margem_final': pct(resultado_final),
        **{g: round(grupos[g], 2) for g in GRUPOS_DESPESA},
        'estrutura': estrutura,
        'grupos_drill': grupos_drill,
        'serie': serie_mensal,
    }
