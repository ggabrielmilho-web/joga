"""Rotas do módulo JOGA Operações (logística): DRE, Embarques e Mapa.

Dados de SQLite semeado (data/demo.sqlite). Sem APIs externas.
"""
from flask import render_template, jsonify, request, abort, session
from . import operacoes_bp
from . import data
from . import dre_demo
from shared.auth import login_required

NAV = 'operacoes'


# ──────────────────────────── páginas ────────────────────────────
@operacoes_bp.route('/')
@login_required
def home():
    return render_template('operacoes/embarques.html', active='operacoes')


@operacoes_bp.route('/dre')
@login_required
def dre_page():
    return render_template('operacoes/dre.html', active='operacoes')


@operacoes_bp.route('/embarques')
@login_required
def embarques_page():
    return render_template('operacoes/embarques.html', active='operacoes')


@operacoes_bp.route('/mapa')
@login_required
def mapa_page():
    return render_template('operacoes/mapa.html', active='operacoes')


# ──────────────────────────── APIs ────────────────────────────
@operacoes_bp.route('/api/dre')
@login_required
def api_dre():
    try:
        meses = int(request.args.get('meses', 12))
    except ValueError:
        meses = 12
    return jsonify(dre_demo.calcular(meses))


@operacoes_bp.route('/api/embarques/kpis')
@login_required
def api_kpis():
    return jsonify({'ok': True, **data.kpis_embarques()})


@operacoes_bp.route('/api/embarques/cargas')
@login_required
def api_cargas():
    status = request.args.get('status') or None
    busca = request.args.get('busca') or None
    return jsonify({'ok': True, 'cargas': data.cargas(status, busca)})


@operacoes_bp.route('/api/embarques/cargas/<int:carga_id>')
@login_required
def api_carga(carga_id):
    c = data.carga(carga_id)
    if not c:
        abort(404)
    return jsonify({'ok': True, 'carga': c})


@operacoes_bp.route('/api/rastreamento/posicoes')
@login_required
def api_posicoes():
    return jsonify({'ok': True, 'posicoes': data.posicoes()})


@operacoes_bp.route('/api/embarques/cidades')
@login_required
def api_cidades():
    return jsonify({'ok': True, 'cidades': data.cidades()})


@operacoes_bp.route('/api/embarques/cargas', methods=['POST'])
@login_required
def api_criar_carga():
    if session.get('role') == 'viewer':
        return jsonify({'ok': False, 'error': 'Visitante não pode lançar embarque.'}), 403
    payload = request.get_json(silent=True) or {}
    obrig = ['cliente', 'origem', 'destino', 'motorista', 'placa']
    falta = [c for c in obrig if not (payload.get(c) or '').strip()]
    if falta:
        return jsonify({'ok': False, 'error': 'Preencha: ' + ', '.join(falta)}), 400
    novo_id, erro = data.criar_carga(payload)
    if erro:
        return jsonify({'ok': False, 'error': erro}), 400
    return jsonify({'ok': True, 'id': novo_id})
