"""Rotas do módulo JOGA Comercial (analytics).

Páginas renderizam templates (extends _shell.html). APIs devolvem JSON
computado dos dados sintéticos via loaders_demo, reusando rfm/cohort.
"""
import csv
import io
from flask import (
    render_template, jsonify, request, session, redirect, Response, abort
)

from . import comercial_bp
from . import loaders_demo as L
from . import rfm
from shared.auth import login_required, rbac_scope, pode_acessar_vendedor

NAV = 'comercial'


# ──────────────────────────── páginas ────────────────────────────
@comercial_bp.route('/')
@login_required
def dashboard():
    return render_template('comercial/index.html', active='dashboard')


@comercial_bp.route('/carteira')
@login_required
def carteira_page():
    return render_template('comercial/carteira.html', active='carteira')


@comercial_bp.route('/vendedores')
@login_required
def vendedores_page():
    # vendedor não vê ranking — vai pro próprio cockpit
    if session.get('role') == 'vendedor':
        return redirect(f"/comercial/vendedor/{session.get('codusur')}")
    return render_template('comercial/vendedores.html', active='vendedores')


@comercial_bp.route('/vendedor/<int:codusur>')
@login_required
def vendedor_page(codusur):
    if not pode_acessar_vendedor(codusur, L.vendedores_map()):
        if session.get('role') == 'vendedor':
            return redirect(f"/comercial/vendedor/{session.get('codusur')}")
        abort(403)
    return render_template('comercial/vendedor.html', active='vendedores', codusur=codusur)


@comercial_bp.route('/tendencias')
@login_required
def tendencias_page():
    return render_template('comercial/tendencias.html', active='tendencias')


@comercial_bp.route('/categorias')
@login_required
def categorias_page():
    return render_template('comercial/categorias.html', active='categorias')


@comercial_bp.route('/mix')
@login_required
def mix_page():
    return render_template('comercial/mix.html', active='mix')


# ──────────────────────────── dashboard API ────────────────────────────
@comercial_bp.route('/api/dashboard/kpis')
@login_required
def api_kpis():
    return jsonify(L.kpis())


@comercial_bp.route('/api/dashboard/serie')
@login_required
def api_serie():
    try:
        meses = int(request.args.get('meses', 12))
    except ValueError:
        meses = 12
    return jsonify({'ok': True, 'rows': L.serie_mensal(meses)})


@comercial_bp.route('/api/dashboard/sazonalidade')
@login_required
def api_sazon():
    return jsonify({'ok': True, 'rows': L.sazonalidade()})


@comercial_bp.route('/api/dashboard/top-clientes')
@login_required
def api_top_clientes():
    metrica = request.args.get('metrica', 'lucro')
    try:
        limit = max(3, min(int(request.args.get('limit', 10)), 50))
    except ValueError:
        limit = 10
    return jsonify({'ok': True, 'rows': L.top_clientes(metrica, limit), 'metrica': metrica})


@comercial_bp.route('/api/dashboard/pareto')
@login_required
def api_pareto():
    try:
        top = max(5, min(int(request.args.get('top', 50)), 200))
    except ValueError:
        top = 50
    return jsonify({'ok': True, 'rows': L.pareto(top), 'top': top})


# ──────────────────────────── carteira API ────────────────────────────
@comercial_bp.route('/api/carteira/rfm')
@login_required
def api_carteira_rfm():
    cli = L.carteira_full()
    agg = rfm.agregar_distribuicoes(cli, 'personalizada')
    ufs = sorted({c['uf'] for c in cli if c['uf']})
    vmap = L.vendedores_map()
    vend_ativos = sorted(
        ({'codusur': int(k), 'nome': v['nome'], 'codsupervisor': v['codsupervisor']}
         for k, v in vmap.items() if any(str(c['codusur']) == k for c in cli)),
        key=lambda x: x['nome'])
    times = sorted({(c.get('codsupervisor'), c.get('time')) for c in cli if c.get('time')})
    return jsonify({
        'ok': True,
        'modo': 'personalizada',
        'regua': agg['regua'],
        'segmentos': agg['segmentos'],
        'total_clientes': agg['total_clientes'],
        'matriz_rf': rfm.matriz_rf(cli),
        'histograma_recencia': rfm.histograma_recencia(cli),
        'ufs_ativas': ufs,
        'vendedores_ativos': vend_ativos,
        'times_ativos': [{'codsupervisor': t[0], 'nome': t[1]} for t in times],
    })


@comercial_bp.route('/api/carteira/clientes')
@login_required
def api_carteira_clientes():
    return jsonify(L.filtrar_carteira(L.carteira_full(), request.args))


@comercial_bp.route('/api/carteira/cliente/<int:codcli>')
@login_required
def api_carteira_cliente(codcli):
    cli = next((c for c in L.carteira_full() if c['codcli'] == codcli), None)
    if not cli:
        abort(404)
    # histórico mensal do cliente + top deptos (dos dados sintéticos)
    ds = L._dataset()
    raw = next((c for c in ds['clientes'] if c['codcli'] == codcli), {})
    historico = [{'AnoMes': am, 'VendaLiquida': v['venda'], 'LucroTotal': v['lucro']}
                 for am, v in sorted(raw.get('mensal', {}).items())]
    dmap = ds['deptos']
    deptos = sorted(
        ({'codepto': cod, 'nome': dmap.get(cod, cod),
          'venda': v['venda'], 'lucro': v['lucro']}
         for cod, v in raw.get('deptos', {}).items()),
        key=lambda x: -x['venda'])[:5]
    return jsonify({'ok': True, 'cliente': cli, 'historico': historico, 'deptos': deptos})


@comercial_bp.route('/api/carteira/csv')
@login_required
def api_carteira_csv():
    args = dict(request.args)
    args['limit'] = 100000
    dados = L.filtrar_carteira(L.carteira_full(), args)
    cols = ['codcli', 'cliente', 'cidade', 'uf', 'codusur', 'vendedor', 'segmento',
            'status_personalizada', 'recencia_dias', 'frequencia_12m',
            'venda_12m', 'lucro_12m', 'receita_perdida_proj']

    def gen():
        buf = io.StringIO()
        buf.write('﻿')  # BOM p/ Excel
        w = csv.writer(buf, delimiter=';')
        w.writerow(cols)
        yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        for r in dados['rows']:
            w.writerow([r.get(c) for c in cols])
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)

    return Response(gen(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=carteira_joga_demo.csv'})


# ──────────────────────────── vendedores API ────────────────────────────
@comercial_bp.route('/api/vendedores')
@login_required
def api_vendedores():
    if session.get('role') == 'vendedor':
        return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
    linhas = L.ranking_vendedores()
    # filtros simples
    tipo = request.args.get('tipovend')
    uf = request.args.get('uf')
    sup = request.args.get('supervisor')
    busca = (request.args.get('busca') or '').strip().lower()
    if tipo:
        linhas = [l for l in linhas if l['tipo'] == tipo]
    if uf:
        linhas = [l for l in linhas if l['estado'] == uf]
    if sup:
        linhas = [l for l in linhas if str(l['codsupervisor']) == str(sup)]
    if busca:
        linhas = [l for l in linhas if busca in l['nome'].lower() or busca in str(l['codusur'])]
    return jsonify({'ok': True, 'total': len(linhas), 'vendedores': linhas})


@comercial_bp.route('/api/vendedor/<int:codusur>')
@login_required
def api_vendedor(codusur):
    if not pode_acessar_vendedor(codusur, L.vendedores_map()):
        return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
    perfil = L.perfil_vendedor(codusur)
    if not perfil:
        abort(404)
    ranking = {l['codusur']: l for l in L.ranking_vendedores()}
    r = ranking.get(codusur, {})
    cart = L.carteira_vendedor(codusur)
    agg = rfm.agregar_distribuicoes(cart, 'personalizada')
    media_taxa = (sum(x['taxa_positivacao'] for x in ranking.values()) / len(ranking)) if ranking else 0
    return jsonify({
        'ok': True, 'perfil': perfil,
        'kpis': {
            'venda_liq': r.get('venda_liq', 0), 'lucro': r.get('lucro', 0),
            'ticket_medio': r.get('ticket_medio', 0),
            'taxa_positivacao': r.get('taxa_positivacao', 0), 'rank': r.get('rank'),
            'yoy_receita': r.get('yoy_receita', 0),
        },
        'carteira': {
            'cadastrados': len(cart),
            'positivados': sum(1 for c in cart if c['frequencia_12m'] >= 1),
            'champions': agg['segmentos'].get('champions', 0),
            'at_risk': agg['segmentos'].get('at_risk', 0),
        },
        'comparativo_equipe': {
            'sua_taxa': r.get('taxa_positivacao', 0),
            'media_equipe': round(media_taxa, 1),
        },
        'segmentos': agg['segmentos'],
    })


@comercial_bp.route('/api/vendedor/<int:codusur>/serie')
@login_required
def api_vendedor_serie(codusur):
    if not pode_acessar_vendedor(codusur, L.vendedores_map()):
        return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
    return jsonify({'ok': True, 'rows': L.serie_vendedor(codusur)})


@comercial_bp.route('/api/vendedor/<int:codusur>/carteira')
@login_required
def api_vendedor_carteira(codusur):
    if not pode_acessar_vendedor(codusur, L.vendedores_map()):
        return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
    return jsonify(L.filtrar_carteira(L.carteira_vendedor(codusur), request.args))


@comercial_bp.route('/api/vendedor/<int:codusur>/alertas')
@login_required
def api_vendedor_alertas(codusur):
    if not pode_acessar_vendedor(codusur, L.vendedores_map()):
        return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
    cart = L.carteira_vendedor(codusur)
    at_risk = [c for c in cart if c['segmento'] in ('at_risk', 'cant_lose')]
    valor_risco = sum(c['receita_perdida_proj'] for c in at_risk)
    champions = sorted([c for c in cart if c['segmento'] == 'champions'],
                       key=lambda c: -(c['lucro_12m'] or 0))[:3]
    return jsonify({'ok': True, 'alertas': [
        {'tipo': 'at_risk', 'qtd': len(at_risk), 'valor': round(valor_risco, 2)},
        {'tipo': 'champions_top3', 'clientes': [
            {'codcli': c['codcli'], 'cliente': c['cliente'], 'lucro_12m': c['lucro_12m']}
            for c in champions]},
    ]})


# ──────────────────────────── tendências / cohort ────────────────────────────
@comercial_bp.route('/api/tendencias/cohort')
@login_required
def api_cohort():
    try:
        periodo = int(request.args.get('periodo', 12))
    except ValueError:
        periodo = 12
    vendedor = request.args.get('vendedor')
    return jsonify({'ok': True, 'cohorts': L.cohort_matriz(periodo, vendedor)})


# ──────────────────────────── categorias / mix ────────────────────────────
@comercial_bp.route('/api/categorias')
@login_required
def api_categorias():
    cats = L.categorias()
    return jsonify({'ok': True, 'total_venda': round(sum(c['venda'] for c in cats), 2),
                    'categorias': cats})


@comercial_bp.route('/api/mix/abandonado')
@login_required
def api_mix():
    try:
        dias = int(request.args.get('dias', 60))
    except ValueError:
        dias = 60
    codepto = request.args.get('codepto')
    rows = L.mix_abandonado(dias, codepto, 100)
    return jsonify({'ok': True, 'dias': dias, 'total': len(rows), 'rows': rows})


# ──────────────────────────── internos ────────────────────────────
@comercial_bp.route('/api/_internal/vendedores-map')
@login_required
def api_vmap():
    return jsonify({'ok': True, 'vendedores': L.vendedores_map()})


@comercial_bp.route('/api/_internal/supervisores-map')
@login_required
def api_smap():
    return jsonify({'ok': True, 'supervisores': L.supervisores_map()})
