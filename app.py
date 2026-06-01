"""JOGA Soluções Empresariais — App de portfólio (demo).

App Flask único, dois módulos via blueprints:
  /comercial/*  → JOGA Comercial (analytics)
  /operacoes/*  → JOGA Operações (logística)

Rode:  python -X utf8 app.py   →  http://localhost:5000
Dados: python -X utf8 data/seed_demo.py --all  (gera a base sintética)
"""
import os
from flask import Flask, render_template, redirect, request, session, jsonify

import config
from shared.auth import login_required, login_session, ROLE_LABEL
from shared.auth_db import autenticar, init_auth

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = config.SECRET_KEY

# Blueprints dos módulos
from comercial import comercial_bp
from operacoes import operacoes_bp
app.register_blueprint(comercial_bp, url_prefix='/comercial')
app.register_blueprint(operacoes_bp, url_prefix='/operacoes')


# Contexto disponível em todos os templates (marca + dados do usuário)
@app.context_processor
def inject_globais():
    return {
        'MARCA': config.MARCA,
        'MARCA_FULL': config.MARCA_FULL,
        'EMPRESA_EXEMPLO': config.EMPRESA_EXEMPLO,
        'user_nome': session.get('nome'),
        'user_role': session.get('role'),
        'user_role_label': ROLE_LABEL.get(session.get('role'), ''),
    }


# ── Landing / seletor de módulo ──
@app.route('/')
@login_required
def landing():
    return render_template('landing.html', active='home')


# ── Login (e-mail + senha) ──
@app.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_post():
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip()
    senha = data.get('senha') or ''
    user = autenticar(email, senha)
    if user:
        login_session(user)
        return jsonify({'ok': True, 'redirect': '/'})
    return jsonify({'ok': False, 'error': 'E-mail ou senha inválidos'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/api/me')
@login_required
def api_me():
    return jsonify({
        'ok': True,
        'nome': session.get('nome'),
        'role': session.get('role'),
        'codusur': session.get('codusur'),
        'codsupervisor': session.get('codsupervisor'),
        'tipos_permitidos': session.get('tipos_permitidos', []),
    })


if __name__ == '__main__':
    print(f"\n  {config.MARCA_FULL} — portfólio demo")
    init_auth()  # garante database + tabela joga_users + admin
    print("  http://localhost:5000\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
