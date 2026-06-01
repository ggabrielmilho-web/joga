"""Gerador de dados sintéticos do módulo Operações (logística) → SQLite.

Tabelas: cargas (embarques + posição atual p/ mapa) e dre_mensal (financeiro).
Tudo fictício. Chamado por seed_demo.gerar_logistica().
"""
import sqlite3
from datetime import timedelta

# cidades com coordenadas (lat, lng) — subset fictício-realista
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
CIDADES = list(CIDADES_GEO)

MOTORISTAS = ['Antônio Ferreira', 'Benedito Alves', 'Cláudio Ramos', 'Domingos Sá',
              'Edson Pires', 'Fernando Luz', 'Geraldo Matos', 'Hélio Braga',
              'Ivo Santana', 'Jonas Vieira', 'Laércio Pinto', 'Moacir Dias']
CLIENTES_LOG = ['Atacadão Central', 'Rede Mais Supermercados', 'Distribuidora Norte',
                'Comercial Bandeirante', 'Grupo Vale Verde', 'Mercantil Estrela',
                'Casa do Construtor', 'Frigorífico Bom Boi', 'Lojas Avenida']
STATUS = ['Aberta', 'Em rota', 'Em rota', 'Em rota', 'Entregue', 'Entregue', 'Cancelada']

# ─────────── Estrutura contábil do DRE (evento → grupo, subgrupo, peso) ───────────
# peso = fração da RECEITA BRUTA que o evento representa (média; com jitter no mês).
# Grupos seguem a cascata obrigatória do DRE. Proporções realistas p/ transporte.
DRE_EVENTOS = [
    # (evento, grupo, subgrupo, peso% da receita)
    # ── Deduções (~10%) ──
    ('ISS sobre serviços',        'Deduções', 'Impostos sobre Serviço', 0.030),
    ('PIS',                       'Deduções', 'Impostos sobre Serviço', 0.016),
    ('COFINS',                    'Deduções', 'Impostos sobre Serviço', 0.038),
    ('ICMS',                      'Deduções', 'Impostos sobre Serviço', 0.018),
    # ── Custo Operacional (~58%) ──
    ('Combustíveis e Lubrificantes', 'Custo Operacional', 'Combustível',   0.205),
    ('Salários Motoristas',          'Custo Operacional', 'Mão de Obra',   0.150),
    ('Encargos Operacionais',        'Custo Operacional', 'Mão de Obra',   0.045),
    ('Manutenção de Veículos',       'Custo Operacional', 'Manutenção',    0.060),
    ('Peças e Acessórios',           'Custo Operacional', 'Manutenção',    0.025),
    ('Pneus e Recapagem',            'Custo Operacional', 'Pneus',         0.030),
    ('Pedágios',                     'Custo Operacional', 'Deslocamento',  0.028),
    ('Diárias de Viagem',            'Custo Operacional', 'Deslocamento',  0.012),
    ('Seguro de Cargas',             'Custo Operacional', 'Seguros',       0.018),
    ('Frete de Terceiros',           'Custo Operacional', 'Fretes',        0.040),
    # ── Despesas Administrativas (~15%) ──
    ('Salários Administrativos',  'Despesas Administrativas', 'Mão de Obra Adm', 0.055),
    ('Encargos Administrativos',  'Despesas Administrativas', 'Encargos',        0.020),
    ('Aluguel e Estrutura',       'Despesas Administrativas', 'Estrutura',       0.022),
    ('Energia, Água e Telefone',  'Despesas Administrativas', 'Estrutura',       0.010),
    ('Software e Sistemas',       'Despesas Administrativas', 'Sistemas',        0.012),
    ('Vale Refeição/Transporte',  'Despesas Administrativas', 'Benefícios',      0.014),
    ('Taxas e Licenças',          'Despesas Administrativas', 'Taxas',           0.009),
    ('Despesas Comerciais',       'Despesas Administrativas', 'Comercial',       0.008),
    # ── Despesas Financeiras (~3%) ──
    ('Juros e Encargos',          'Despesas Financeiras', 'Custos Financeiros', 0.020),
    ('IOF',                       'Despesas Financeiras', 'Custos Financeiros', 0.005),
    ('Tarifas Bancárias',         'Despesas Financeiras', 'Custos Financeiros', 0.005),
    # ── Impostos (~3%) ──
    ('IRPJ',                      'Impostos', 'Impostos sobre Lucro', 0.018),
    ('CSLL',                      'Impostos', 'Impostos sobre Lucro', 0.012),
    # ── Investimentos (~2,2%) ──
    ('Aquisição de Veículos',     'Investimentos', 'Imobilizado', 0.015),
    ('Consórcio de Frota',        'Investimentos', 'Imobilizado', 0.007),
    # ── Retiradas (~2,3%) ──
    ('Pró-labore Sócios',         'Retiradas', 'Distribuição', 0.015),
    ('Distribuição de Lucros',    'Retiradas', 'Distribuição', 0.008),
]


def _interp(o, d, t):
    return (o[0] + (d[0] - o[0]) * t, o[1] + (d[1] - o[1]) * t)


def gerar(sqlite_path, rng, hoje):
    conn = sqlite3.connect(str(sqlite_path))
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS cargas;
        DROP TABLE IF EXISTS dre_mensal;
        CREATE TABLE cargas(
            id INTEGER PRIMARY KEY, status TEXT, motorista TEXT, placa TEXT,
            cliente TEXT, origem TEXT, destino TEXT, origem_lat REAL, origem_lng REAL,
            destino_lat REAL, destino_lng REAL, pos_lat REAL, pos_lng REAL,
            progresso INTEGER, peso_kg REAL, valor_frete REAL, distancia_km REAL,
            data_saida TEXT, previsao TEXT
        );
        CREATE TABLE dre_mensal(
            anomes TEXT, tipo TEXT, grupo TEXT, subgrupo TEXT, evento TEXT, valor REAL
        );
    """)

    for i in range(1, 41):
        status = rng.choice(STATUS)
        oc, dc = rng.sample(CIDADES, 2)
        o, d = CIDADES_GEO[oc], CIDADES_GEO[dc]
        dist = round(((o[0]-d[0])**2 + (o[1]-d[1])**2) ** 0.5 * 111, 1)
        if status == 'Em rota':
            prog = rng.randint(15, 85)
        elif status == 'Entregue':
            prog = 100
        elif status == 'Cancelada':
            prog = rng.randint(0, 60)
        else:
            prog = 0
        pos = _interp(o, d, prog/100)
        saida = hoje - timedelta(days=rng.randint(0, 25))
        placa = f"{rng.choice('BCDFGHJ')}{rng.choice('AEIOU')}{rng.choice('LMNPR')}{rng.randint(1000,9999)}"
        cur.execute("""INSERT INTO cargas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            i, status, rng.choice(MOTORISTAS), placa[:3].upper()+'-'+placa[3:],
            rng.choice(CLIENTES_LOG), oc, dc, o[0], o[1], d[0], d[1],
            round(pos[0], 5), round(pos[1], 5), prog,
            round(rng.uniform(800, 28000), 0), round(rng.uniform(1200, 18000), 2), dist,
            saida.isoformat(), (saida + timedelta(days=max(1, int(dist/600)))).isoformat(),
        ))

    # DRE: 12 meses
    base_receita = 1_350_000
    y, m = hoje.year, hoje.month
    meses = []
    for _ in range(12):
        meses.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12; y -= 1
    meses.reverse()
    for idx, am in enumerate(meses):
        sazon = 1 + 0.12 * ((idx % 12) / 11)
        receita = round(base_receita * sazon * rng.uniform(0.94, 1.06) * (1 + 0.012 * idx), 2)
        cur.execute("INSERT INTO dre_mensal VALUES (?,?,?,?,?,?)",
                    (am, 'receita', 'Receita Bruta', 'Receita de Fretes', 'Receita de Fretes', receita))
        # cada evento de despesa = peso% da receita bruta (com jitter mensal)
        for ev, grupo, subgrupo, peso in DRE_EVENTOS:
            valor = round(receita * peso * rng.uniform(0.9, 1.1), 2)
            cur.execute("INSERT INTO dre_mensal VALUES (?,?,?,?,?,?)",
                        (am, 'despesa', grupo, subgrupo, ev, valor))

    conn.commit()
    conn.close()
    n = 40
    print(f"[logistica] {n} cargas + DRE 12m → {sqlite_path.name}")
