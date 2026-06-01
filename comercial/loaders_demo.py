"""Loaders sintéticos do módulo Comercial.

Lê data/demo_comercial.json e devolve estruturas no mesmo formato que os
loaders originais produziam — porém calculadas com a lógica RFM/cohort REAL
(rfm.py / cohort.py copiados verbatim). RBAC aplicado por escopo de sessão.
"""
import json
from datetime import date, timedelta
from functools import lru_cache

import config
from shared.auth import rbac_scope
from . import rfm
from . import cohort

VENDEDORES_TECNICOS = {999, 900, 4, 272}


@lru_cache(maxsize=1)
def _dataset():
    with open(config.COMERCIAL_JSON, encoding='utf-8') as fh:
        return json.load(fh)


def anchor():
    return date.fromisoformat(_dataset()['anchor'])


# ───────────────────────── mapas ─────────────────────────
def vendedores_map():
    """{str(codusur): {nome, tipo, codsupervisor, cidade, estado, bloqueio}}"""
    return {str(v['codusur']): v for v in _dataset()['vendedores']}


def supervisores_map():
    """{str(codsupervisor): nome}"""
    return _dataset()['supervisores']


def deptos_map():
    """{str(codepto): nome}"""
    return _dataset()['deptos']


def fornecedores():
    return _dataset()['fornecedores']


# ───────────────────────── carteira (RFM real) ─────────────────────────
@lru_cache(maxsize=1)
def _carteira_base():
    """Roda rfm.calcular_clientes uma vez sobre toda a base e enriquece."""
    ds = _dataset()
    cl = ds['clientes']
    vmap = {str(v['codusur']): v for v in ds['vendedores']}
    smap = ds['supervisores']

    snapshot = [dict(CODCLI=c['codcli'], **c['snapshot']) for c in cl]
    datas = {c['codcli']: c['datas'] for c in cl}
    meta = {c['codcli']: {
        'cliente': c['cliente'], 'fantasia': c.get('fantasia'),
        'cidade': c['cidade'], 'uf': c['uf'],
        'telefone': c['telefone'], 'codusur1': c['codusur1'],
        'bloqueio': c['bloqueio'],
    } for c in cl}

    res = rfm.calcular_clientes(snapshot, datas, meta)
    # enriquecimento vendedor / supervisor / time
    for r in res:
        v = vmap.get(str(r['codusur'])) or {}
        r['vendedor'] = v.get('nome')
        r['codsupervisor'] = v.get('codsupervisor')
        r['time'] = smap.get(str(v.get('codsupervisor')))
    return res


def carteira_full():
    """Carteira completa filtrada pelo escopo RBAC do usuário logado."""
    base = _carteira_base()
    codusur, codsupervisor = rbac_scope()
    if codusur is not None:
        return [c for c in base if str(c['codusur']) == str(codusur)]
    if codsupervisor is not None:
        return [c for c in base if str(c.get('codsupervisor')) == str(codsupervisor)]
    return base


def filtrar_carteira(clientes, args):
    """Filtros/ordenação/paginação em memória (espelha _filtrar_carteira original)."""
    uf = (args.get('uf') or '').strip()
    cidade = (args.get('cidade') or '').strip().lower()
    vendedor = (args.get('vendedor') or '').strip()
    segmentos = [s for s in (args.get('segmento') or '').split(',') if s]
    status = [s for s in (args.get('status') or '').split(',') if s]
    busca = (args.get('busca') or '').strip().lower()
    ordenar = args.get('ordenar', 'receita_perdida')
    try:
        limit = max(1, min(int(args.get('limit', 50)), 1000))
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(0, int(args.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    rows = clientes
    if uf:
        rows = [c for c in rows if c['uf'] == uf]
    if cidade:
        rows = [c for c in rows if (c['cidade'] or '').lower() == cidade]
    if vendedor:
        rows = [c for c in rows if str(c['codusur']) == str(vendedor)]
    if segmentos:
        rows = [c for c in rows if c['segmento'] in segmentos]
    if status:
        rows = [c for c in rows if c['status_personalizada'] in status]
    if busca:
        def _match(c):
            campos = [c.get('cliente'), c.get('cidade'), str(c.get('codcli')),
                      str(c.get('codusur')), c.get('vendedor'), c.get('time')]
            return any(busca in (str(x).lower()) for x in campos if x)
        rows = [c for c in rows if _match(c)]

    chave = {
        'receita_perdida': lambda c: -(c['receita_perdida_proj'] or 0),
        'lucro_perdido':   lambda c: -(c['lucro_perdido_proj'] or 0),
        'lucro_12m':       lambda c: -(c['lucro_12m'] or 0),
        'venda_12m':       lambda c: -(c['venda_12m'] or 0),
        'recencia':        lambda c: c['recencia_dias'],
        'frequencia':      lambda c: -(c['frequencia_12m'] or 0),
        'cliente':         lambda c: (c['cliente'] or '').lower(),
    }.get(ordenar, lambda c: -(c['receita_perdida_proj'] or 0))
    rows = sorted(rows, key=chave)

    total = len(rows)
    segmentos_count = {}
    for c in rows:
        segmentos_count[c['segmento']] = segmentos_count.get(c['segmento'], 0) + 1
    return {
        'ok': True, 'total': total, 'offset': offset, 'limit': limit,
        'rows': rows[offset:offset + limit], 'segmentos': segmentos_count,
    }


# ───────────────────────── séries / dashboard ─────────────────────────
def _meses_window(n):
    """Lista de 'YYYY-MM' dos últimos n meses até o anchor (inclusive)."""
    a = anchor().replace(day=1)
    out = []
    y, m = a.year, a.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def serie_mensal(meses=12):
    """Soma venda/lucro por mês, respeitando RBAC (soma sobre carteira no escopo)."""
    cli = carteira_full()
    codclis = {c['codcli'] for c in cli}
    ds = _dataset()
    janela = set(_meses_window(meses))
    acc = {}
    for c in ds['clientes']:
        if c['codcli'] not in codclis:
            continue
        for am, v in c['mensal'].items():
            if am in janela:
                a = acc.setdefault(am, {'VendaLiquida': 0.0, 'LucroTotal': 0.0, 'clientes': set()})
                a['VendaLiquida'] += v['venda']
                a['LucroTotal'] += v['lucro']
                a['clientes'].add(c['codcli'])
    return [{'AnoMes': am, 'VendaLiquida': round(acc[am]['VendaLiquida'], 2),
             'LucroTotal': round(acc[am]['LucroTotal'], 2),
             'ClientesUnicos': len(acc[am]['clientes'])}
            for am in sorted(acc)]


def kpis():
    """KPIs dos últimos 12m + YoY (12m vs 12m anterior)."""
    serie24 = serie_mensal(24)
    ult12 = serie24[-12:]
    ant12 = serie24[-24:-12]
    cli = carteira_full()

    venda12 = sum(s['VendaLiquida'] for s in ult12)
    lucro12 = sum(s['LucroTotal'] for s in ult12)
    venda_ant = sum(s['VendaLiquida'] for s in ant12) or 1
    lucro_ant = sum(s['LucroTotal'] for s in ant12) or 1
    margem = (lucro12 / venda12 * 100) if venda12 else 0
    ativos = [c for c in cli if c['frequencia_12m'] >= 1]
    n_compras = sum(c['frequencia_12m'] for c in cli) or 1
    ticket = venda12 / n_compras
    clientes_positivados = len(ativos)
    pos_ant = max(1, sum(1 for s in ant12) and len(ativos))  # aproximação
    novos = sum(1 for c in cli if c['segmento'] == 'new')

    def _yoy(atual, ant):
        return round((atual - ant) / ant * 100, 1) if ant else 0

    return {
        'ok': True,
        'primarios': {
            'venda_liquida': round(venda12, 2),
            'lucro_total': round(lucro12, 2),
            'margem': round(margem, 2),
            'ticket_medio': round(ticket, 2),
        },
        'secundarios': {
            'clientes_positivados': clientes_positivados,
            'clientes_novos': novos,
            'clientes_ativos': len(ativos),
            'total_clientes': len(cli),
        },
        'yoy': {
            'receita_liquida': _yoy(venda12, venda_ant),
            'lucro_bruto': _yoy(lucro12, lucro_ant),
        },
    }


def top_clientes(metrica='lucro', limit=10):
    cli = carteira_full()
    chave = 'lucro_12m' if metrica == 'lucro' else 'venda_12m'
    rows = sorted(cli, key=lambda c: -(c[chave] or 0))[:limit]
    return [{'CODCLI': c['codcli'], 'CLIENTE': c['cliente'], 'UF': c['uf'],
             'CODUSUR': c['codusur'], 'VENDEDOR': c['vendedor'],
             'Lucro12m': c['lucro_12m'], 'Venda12m': c['venda_12m']} for c in rows]


def pareto(top=50):
    cli = carteira_full()
    rows = sorted(cli, key=lambda c: -(c['venda_12m'] or 0))[:top]
    return [{'CODCLI': c['codcli'], 'CLIENTE': c['cliente'], 'UF': c['uf'],
             'Venda12m': c['venda_12m']} for c in rows]


def sazonalidade():
    """Venda por (ano, mês) últimos 24m, respeitando RBAC."""
    serie = serie_mensal(24)
    out = []
    for s in serie:
        ano, mes = s['AnoMes'].split('-')
        out.append({'Ano': int(ano), 'MES': int(mes), 'VendaLiquida': s['VendaLiquida']})
    return out


# ───────────────────────── vendedores ─────────────────────────
def ranking_vendedores():
    """Ranking com venda/lucro/ticket/positivação 12m + YoY, respeitando RBAC."""
    ds = _dataset()
    vmap = {str(v['codusur']): v for v in ds['vendedores']}
    smap = ds['supervisores']
    codusur, codsupervisor = rbac_scope()
    janela12 = set(_meses_window(12))
    janela_ant = set(_meses_window(24)) - janela12

    agg = {}
    base = _carteira_base()
    # clientes por vendedor (para positivação/carteira)
    cli_por_vend = {}
    for c in base:
        cli_por_vend.setdefault(str(c['codusur']), []).append(c)

    for c in ds['clientes']:
        cu = str(c['codusur1'])
        a = agg.setdefault(cu, {'venda12': 0.0, 'lucro12': 0.0, 'venda_ant': 0.0, 'notas12': 0})
        for am, v in c['mensal'].items():
            if am in janela12:
                a['venda12'] += v['venda']
                a['lucro12'] += v['lucro']
            elif am in janela_ant:
                a['venda_ant'] += v['venda']
        a['notas12'] += sum(1 for dt in c['datas'] if dt[:7] in janela12)

    linhas = []
    for cu, v in vmap.items():
        if int(cu) in VENDEDORES_TECNICOS or v.get('bloqueio') == 'S':
            continue
        a = agg.get(cu, {'venda12': 0, 'lucro12': 0, 'venda_ant': 0, 'notas12': 0})
        cli = cli_por_vend.get(cu, [])
        positivados = sum(1 for c in cli if c['frequencia_12m'] >= 1)
        cadastrados = len(cli)
        venda_ant = a['venda_ant'] or 0
        yoy = round((a['venda12'] - venda_ant) / venda_ant * 100, 1) if venda_ant else 0
        ticket = (a['venda12'] / a['notas12']) if a['notas12'] else 0
        taxa = (positivados / cadastrados * 100) if cadastrados else 0
        if a['venda12'] <= 0:
            continue
        linhas.append({
            'codusur': int(cu), 'nome': v['nome'], 'tipo': v['tipo'],
            'codsupervisor': v['codsupervisor'], 'time': smap.get(str(v['codsupervisor'])),
            'cidade': v['cidade'], 'estado': v['estado'],
            'venda_liq': round(a['venda12'], 2), 'lucro': round(a['lucro12'], 2),
            'ticket_medio': round(ticket, 2), 'taxa_positivacao': round(taxa, 1),
            'clientes_unicos': positivados, 'cadastrados': cadastrados,
            'yoy_receita': yoy,
        })

    # RBAC
    if codusur is not None:
        linhas = [l for l in linhas if l['codusur'] == codusur]
    elif codsupervisor is not None:
        linhas = [l for l in linhas if l['codsupervisor'] == codsupervisor]

    linhas.sort(key=lambda l: -l['venda_liq'])
    for i, l in enumerate(linhas, 1):
        l['rank'] = i
    return linhas


def perfil_vendedor(codusur):
    v = vendedores_map().get(str(codusur))
    if not v:
        return None
    smap = supervisores_map()
    return {
        'codusur': int(codusur), 'nome': v['nome'], 'tipo': v['tipo'],
        'cidade': v['cidade'], 'estado': v['estado'],
        'codsupervisor': v['codsupervisor'], 'time': smap.get(str(v['codsupervisor'])),
        'bloqueio': v['bloqueio'],
    }


def serie_vendedor(codusur, meses=12):
    ds = _dataset()
    janela = set(_meses_window(meses))
    acc = {}
    for c in ds['clientes']:
        if str(c['codusur1']) != str(codusur):
            continue
        for am, v in c['mensal'].items():
            if am in janela:
                a = acc.setdefault(am, {'VendaLiquida': 0.0, 'LucroTotal': 0.0})
                a['VendaLiquida'] += v['venda']
                a['LucroTotal'] += v['lucro']
    return [{'AnoMes': am, 'VendaLiquida': round(acc[am]['VendaLiquida'], 2),
             'LucroTotal': round(acc[am]['LucroTotal'], 2)} for am in sorted(acc)]


def carteira_vendedor(codusur):
    return [c for c in _carteira_base() if str(c['codusur']) == str(codusur)]


# ───────────────────────── cohort / tendências ─────────────────────────
def cohort_matriz(periodo_meses=12, codusur=None):
    ds = _dataset()
    rbac_usur, rbac_supv = rbac_scope()
    if rbac_usur is not None:
        codusur = rbac_usur
    compras = {}
    vmap = {str(v['codusur']): v for v in ds['vendedores']}
    for c in ds['clientes']:
        if codusur is not None and str(c['codusur1']) != str(codusur):
            continue
        if rbac_supv is not None:
            v = vmap.get(str(c['codusur1'])) or {}
            if v.get('codsupervisor') != rbac_supv:
                continue
        compras[c['codcli']] = c['datas']
    data = cohort.cohort_de_compras(compras)
    return cohort.matriz_cohort(data, meses_max=periodo_meses)


# ───────────────────────── categorias / mix ─────────────────────────
def categorias():
    ds = _dataset()
    dmap = ds['deptos']
    codclis = {c['codcli'] for c in carteira_full()}
    agg = {}
    for c in ds['clientes']:
        if c['codcli'] not in codclis:
            continue
        for cod, v in c.get('deptos', {}).items():
            a = agg.setdefault(cod, {'venda': 0.0, 'lucro': 0.0, 'clientes': set()})
            a['venda'] += v['venda']
            a['lucro'] += v['lucro']
            a['clientes'].add(c['codcli'])
    total = sum(a['venda'] for a in agg.values()) or 1
    out = []
    for cod, a in agg.items():
        out.append({
            'codepto': cod, 'nome': dmap.get(cod, f'Depto {cod}'),
            'venda': round(a['venda'], 2), 'lucro': round(a['lucro'], 2),
            'margem': round(a['lucro'] / a['venda'] * 100, 1) if a['venda'] else 0,
            'clientes_unicos': len(a['clientes']),
            'share': round(a['venda'] / total * 100, 1),
        })
    out.sort(key=lambda x: -x['venda'])
    return out


def mix_abandonado(dias=60, codepto=None, limit=100):
    """Clientes que não compram um depto há > N dias (vs. mediana histórica)."""
    ds = _dataset()
    dmap = ds['deptos']
    cli_map = {c['codcli']: c for c in carteira_full()}
    out = []
    anchor_d = anchor()
    for c in ds['clientes']:
        cc = cli_map.get(c['codcli'])
        if not cc:
            continue
        for cod, v in c.get('deptos', {}).items():
            if codepto and str(cod) != str(codepto):
                continue
            # última compra do depto = última compra do cliente (aprox.) menos jitter determinístico
            dias_sem = cc['recencia_dias'] + (int(cod) * 7) % 40
            if dias_sem < dias:
                continue
            out.append({
                'codcli': c['codcli'], 'cliente': c['cliente'],
                'cidade': c['cidade'], 'uf': c['uf'],
                'codusur': c['codusur1'], 'vendedor': cc.get('vendedor'),
                'codepto': cod, 'depto_nome': dmap.get(cod, f'Depto {cod}'),
                'dias_sem_comprar': dias_sem,
                'venda_cat_12m': v['venda'],
                'lucro_cat_12m': v['lucro'],
            })
    out.sort(key=lambda x: -x['venda_cat_12m'])
    return out[:limit]
