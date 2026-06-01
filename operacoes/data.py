"""Loaders do módulo Operações — leem o SQLite semeado (data/demo.sqlite).

DRE = dre_demo.calcular() a partir de dre_mensal. Embarques/mapa = tabela cargas.
"""
from datetime import date, timedelta
from shared.db import get_db

# Coordenadas das cidades atendidas (p/ lançar embarque + mapa)
CIDADES_GEO = {
    'Uberlândia/MG': (-18.9186, -48.2772), 'Uberaba/MG': (-19.7472, -47.9381),
    'Belo Horizonte/MG': (-19.9167, -43.9345), 'Araguari/MG': (-18.6469, -48.1873),
    'Patos de Minas/MG': (-18.5789, -46.5181), 'São Paulo/SP': (-23.5505, -46.6333),
    'Campinas/SP': (-22.9056, -47.0608), 'Ribeirão Preto/SP': (-21.1775, -47.8103),
    'Goiânia/GO': (-16.6869, -49.2648), 'Anápolis/GO': (-16.3267, -48.9526),
    'Catalão/GO': (-18.1657, -47.9461), 'Vitória/ES': (-20.3155, -40.3128),
    'Vila Velha/ES': (-20.3297, -40.2925), 'Cariacica/ES': (-20.2636, -40.4163),
    'Rio de Janeiro/RJ': (-22.9068, -43.1729), 'Campos dos Goytacazes/RJ': (-21.7587, -41.3296),
}


def cidades():
    return sorted(CIDADES_GEO.keys())


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def cargas(status=None, busca=None, limit=200):
    conn = get_db(); cur = conn.cursor()
    sql = "SELECT * FROM cargas"
    cond, params = [], []
    if status:
        cond.append("status = ?"); params.append(status)
    if busca:
        cond.append("(LOWER(cliente) LIKE ? OR LOWER(motorista) LIKE ? OR LOWER(destino) LIKE ? OR placa LIKE ?)")
        b = f"%{busca.lower()}%"; params += [b, b, b, busca.upper()+'%']
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY data_saida DESC LIMIT ?"; params.append(limit)
    cur.execute(sql, params)
    out = _rows(cur)
    conn.close()
    return out


def carga(carga_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM cargas WHERE id = ?", (carga_id,))
    r = _rows(cur); conn.close()
    return r[0] if r else None


def kpis_embarques():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) n, COALESCE(SUM(valor_frete),0) v FROM cargas GROUP BY status")
    por = {row[0]: {'n': row[1], 'v': row[2]} for row in cur.fetchall()}
    conn.close()
    return {
        'abertas': por.get('Aberta', {}).get('n', 0),
        'em_rota': por.get('Em rota', {}).get('n', 0),
        'entregues': por.get('Entregue', {}).get('n', 0),
        'frete_total': round(sum(p['v'] for p in por.values()), 2),
    }


def posicoes():
    """Cargas Em rota com posição atual (p/ mapa)."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM cargas WHERE status='Em rota'")
    out = _rows(cur); conn.close()
    return out


def criar_carga(payload):
    """Insere uma nova carga (status Aberta). Retorna o id criado.
    Posição inicial = origem; progresso 0."""
    origem = payload.get('origem'); destino = payload.get('destino')
    o = CIDADES_GEO.get(origem); d = CIDADES_GEO.get(destino)
    if not o or not d or origem == destino:
        return None, 'Origem e destino inválidos.'
    dist = round(((o[0]-d[0])**2 + (o[1]-d[1])**2) ** 0.5 * 111, 1)
    hoje = date.today()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM cargas")
    novo_id = cur.fetchone()[0]
    cur.execute("""INSERT INTO cargas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        novo_id, 'Aberta', payload.get('motorista', ''), payload.get('placa', ''),
        payload.get('cliente', ''), origem, destino, o[0], o[1], d[0], d[1],
        o[0], o[1], 0,
        float(payload.get('peso_kg') or 0), float(payload.get('valor_frete') or 0), dist,
        hoje.isoformat(), (hoje + timedelta(days=max(1, int(dist/600)))).isoformat(),
    ))
    conn.commit(); conn.close()
    return novo_id, None


def dre_mensal():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT anomes, tipo, grupo, subgrupo, evento, valor FROM dre_mensal ORDER BY anomes")
    out = _rows(cur); conn.close()
    return out
