"""Autenticação (e-mail/senha) + RBAC.

A validação de credenciais fica em shared/auth_db.py (Postgres em produção,
SQLite local). Aqui ficam: setar a sessão pós-login, decorators e RBAC.
O RBAC continua real (vendedor vê só a própria carteira, etc.).
"""
import functools
from flask import session, request, jsonify, redirect

ROLE_LABEL = {
    'admin': 'Diretor', 'supervisor': 'Supervisor',
    'vendedor': 'Vendedor', 'viewer': 'Visitante',
}


def login_session(user):
    """Popula a sessão a partir do dict devolvido por auth_db.autenticar()."""
    session.clear()
    session['user_id'] = user['user_id']
    session['nome'] = user['nome']
    session['role'] = user['role']
    session['codusur'] = user.get('codusur')
    session['codsupervisor'] = user.get('codsupervisor')
    session['tipos_permitidos'] = user.get('tipos_permitidos', [])
    session['must_change_password'] = False


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
