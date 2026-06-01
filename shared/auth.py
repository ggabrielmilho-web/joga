"""Autenticação demo + RBAC.

Sem banco de senhas: a tela de login é um seletor de papel (1 clique).
Cada papel injeta na sessão as MESMAS chaves que os dois módulos já leem,
para que o RBAC continue real (vendedor vê só a própria carteira, etc.).
"""
import functools
from flask import session, request, jsonify, redirect

# Usuários demo. codusur/codsupervisor batem com os dados sintéticos do seed.
DEMO_USERS = {
    'diretor': {
        'user_id': 1, 'nome': 'Diretor (Demo)', 'role': 'admin',
        'codusur': None, 'codsupervisor': None,
        'tipos_permitidos': ['receita', 'despesa', 'embarques', 'dre'],
    },
    'supervisor': {
        'user_id': 2, 'nome': 'Supervisor — Equipe Capital', 'role': 'supervisor',
        'codusur': None, 'codsupervisor': 11,
        'tipos_permitidos': ['receita', 'embarques'],
    },
    'vendedor': {
        'user_id': 3, 'nome': 'Vendedor — Carlos Nunes', 'role': 'vendedor',
        'codusur': 107, 'codsupervisor': None,
        'tipos_permitidos': ['receita'],
    },
    'viewer': {
        'user_id': 4, 'nome': 'Visitante (somente leitura)', 'role': 'viewer',
        'codusur': None, 'codsupervisor': None,
        'tipos_permitidos': ['receita', 'despesa', 'embarques', 'dre'],
    },
}

ROLE_LABEL = {
    'admin': 'Diretor', 'supervisor': 'Supervisor',
    'vendedor': 'Vendedor', 'viewer': 'Visitante',
}


def login_como(papel):
    """Seta a sessão com o usuário demo do papel. Retorna False se papel inválido."""
    u = DEMO_USERS.get(papel)
    if not u:
        return False
    session.clear()
    session['user_id'] = u['user_id']
    session['nome'] = u['nome']
    session['role'] = u['role']
    session['codusur'] = u['codusur']
    session['codsupervisor'] = u['codsupervisor']
    session['tipos_permitidos'] = u['tipos_permitidos']
    session['must_change_password'] = False
    return True


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/comercial/api/') or request.path.startswith('/operacoes/api/') or request.path.startswith('/api/'):
                return jsonify({'ok': False, 'error': 'Não autenticado'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'ok': False, 'error': 'Não autenticado'}), 401
        if session.get('role') != 'admin':
            return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def deco(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'ok': False, 'error': 'Não autenticado'}), 401
            if session.get('role') not in roles:
                return jsonify({'ok': False, 'error': 'Acesso negado'}), 403
            return f(*args, **kwargs)
        return decorated
    return deco


def rbac_scope():
    """Devolve (codusur, codsupervisor) do escopo do usuário logado.
    admin/viewer → (None, None) = vê tudo."""
    role = session.get('role')
    if role in ('admin', 'viewer'):
        return None, None
    return session.get('codusur'), session.get('codsupervisor')


def pode_acessar_vendedor(codusur_alvo, vendedores_map=None):
    """admin/viewer: tudo. vendedor: só o próprio. supervisor: só seu time."""
    role = session.get('role')
    if role in ('admin', 'viewer'):
        return True
    if role == 'vendedor':
        return str(session.get('codusur')) == str(codusur_alvo)
    if role == 'supervisor':
        sup = session.get('codsupervisor')
        if vendedores_map:
            info = vendedores_map.get(str(codusur_alvo)) or {}
            return str(info.get('codsupervisor')) == str(sup)
        return False
    return False
