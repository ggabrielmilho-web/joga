"""Radar de Produtos — funções puras (sem Flask/DB/DAX).
Espelha a lógica de _radar_board_full / _radar_status / _radar_detalhe_rows do
Multpel, porém lendo o histórico por produto do dataset sintético em vez de DAX.

Entrada:
- clientes: lista de dicts no escopo do usuário, cada um com meta (codcli, cliente,
  cidade, uf, vendedor, codusur, telefone) + `produtos`: {codprod(str): [[iso, venda, qt], ...]}.
- produtos_map: {codprod(str): {descricao, codepto, codfornec, fornec_nome, depto_nome}}.
- dias: janela recente; a janela anterior é [dias, 2*dias). hoje: date âncora.
"""
from datetime import date

JANELA_12M = 365


def _dist_dias(iso, hoje):
    try:
        return (hoje - date.fromisoformat(iso[:10])).days
    except (ValueError, TypeError):
        return None


def status(dias_parado, venda_rec, venda_ant, dias):
    """Classifica o cliente em relação ao produto:
    perdido (≥2×dias ou nunca) · parou (≥dias) · esfriando (volume caiu >50%) · ativo."""
    if dias_parado is None or dias_parado >= 2 * dias:
        return 'perdido'
    if dias_parado >= dias:
        return 'parou'
    if venda_ant > 0 and venda_rec < 0.5 * venda_ant:
        return 'esfriando'
    return 'ativo'


def board(clientes, produtos_map, dias, hoje):
    """Produtos sangrando (queda de receita: janela anterior − recente), ordenados desc.
    Só entram produtos com queda > 0. Retorna lista de linhas prontas pro board."""
    d2 = 2 * dias
    rec, ant = {}, {}  # codprod -> {'venda':.., 'clientes':set()}
    for c in clientes:
        cc = c['codcli']
        for cp, evs in (c.get('produtos') or {}).items():
            for iso, venda, _qt in evs:
                dd = _dist_dias(iso, hoje)
                if dd is None or dd < 0:
                    continue
                if dd < dias:
                    b = rec.setdefault(cp, {'venda': 0.0, 'clientes': set()})
                elif dd < d2:
                    b = ant.setdefault(cp, {'venda': 0.0, 'clientes': set()})
                else:
                    continue
                b['venda'] += venda
                b['clientes'].add(cc)

    out = []
    for cp in set(rec) | set(ant):
        v_rec = rec.get(cp, {}).get('venda', 0.0)
        v_ant = ant.get(cp, {}).get('venda', 0.0)
        c_rec = len(rec.get(cp, {}).get('clientes', ()))
        c_ant = len(ant.get(cp, {}).get('clientes', ()))
        queda = round(v_ant - v_rec, 2)
        if queda <= 0:
            continue
        info = produtos_map.get(str(cp)) or {}
        out.append({
            'codprod':           int(cp),
            'descricao':         info.get('descricao') or f'Produto {cp}',
            'codepto':           info.get('codepto'),
            'depto_nome':        info.get('depto_nome'),
            'codfornec':         info.get('codfornec'),
            'fornec_nome':       info.get('fornec_nome'),
            'venda_rec':         round(v_rec, 2),
            'venda_ant':         round(v_ant, 2),
            'queda_receita':     queda,
            'pct_queda':         round(queda / v_ant, 4) if v_ant else None,
            'clientes_perdidos': max(0, c_ant - c_rec),
        })
    out.sort(key=lambda x: x['queda_receita'], reverse=True)
    return out


def _agg_produto_cliente(evs, codprod_str, dias, hoje):
    """Agrega os eventos de UM produto de UM cliente: 12m, janelas rec/ant, última."""
    d2 = 2 * dias
    v12 = q12 = v_rec = q_rec = v_ant = q_ant = 0.0
    ultima_dd = None
    for iso, venda, qt in evs:
        dd = _dist_dias(iso, hoje)
        if dd is None or dd < 0:
            continue
        if dd <= JANELA_12M:
            v12 += venda
            q12 += qt
        if ultima_dd is None or dd < ultima_dd:
            ultima_dd = dd
        if dd < dias:
            v_rec += venda; q_rec += qt
        elif dd < d2:
            v_ant += venda; q_ant += qt
    return {
        'venda_12m': round(v12, 2), 'qt_12m': round(q12, 2),
        'venda_rec': round(v_rec, 2), 'qt_rec': round(q_rec, 2),
        'venda_ant': round(v_ant, 2), 'qt_ant': round(q_ant, 2),
        'dias_parado': ultima_dd,
    }


def detalhe(clientes, produtos_map, codprod, dias, hoje):
    """Clientes que compram/compravam o produto, com status/queda/troca-vs-abandono.
    Retorna (info, linhas). Linhas ordenadas por venda_12m desc (potencial de recuperação)."""
    cp = str(codprod)
    info = produtos_map.get(cp) or {}
    codepto = info.get('codepto')

    linhas = []
    for c in clientes:
        evs = (c.get('produtos') or {}).get(cp)
        if not evs:
            continue
        a = _agg_produto_cliente(evs, cp, dias, hoje)
        if a['venda_12m'] <= 0 and a['dias_parado'] is None:
            continue
        st = status(a['dias_parado'], a['venda_rec'], a['venda_ant'], dias)
        parou = st in ('parou', 'perdido')
        # trocou = parou DESTE produto mas comprou OUTRO do mesmo depto na janela recente
        trocou = False
        if parou and codepto is not None:
            for outro_cp, outro_evs in (c.get('produtos') or {}).items():
                if outro_cp == cp:
                    continue
                oinfo = produtos_map.get(str(outro_cp)) or {}
                if oinfo.get('codepto') != codepto:
                    continue
                if any((_dist_dias(e[0], hoje) or 10 ** 9) < dias for e in outro_evs):
                    trocou = True
                    break
        linhas.append({
            'codcli':        c['codcli'],
            'cliente':       c.get('cliente') or f"Cliente #{c['codcli']}",
            'cidade':        c.get('cidade'),
            'uf':            c.get('uf'),
            'vendedor':      c.get('vendedor'),
            'codusur':       c.get('codusur'),
            'telefone':      c.get('telefone'),
            'dias_parado':   a['dias_parado'],
            'venda_12m':     a['venda_12m'],
            'qt_12m':        a['qt_12m'],
            'venda_rec':     a['venda_rec'],
            'venda_ant':     a['venda_ant'],
            'status':        st,
            'trocou':        bool(trocou),
        })
    linhas.sort(key=lambda x: x['venda_12m'], reverse=True)
    return info, linhas
