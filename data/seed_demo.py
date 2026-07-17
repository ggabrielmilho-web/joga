"""Gerador de dados sintéticos do portfólio JOGA.

100% fictício, sem vínculo com clientes reais. RNG com seed fixa → reprodutível.
As DATAS são ancoradas em "hoje" (a demo sempre parece atual), mas as formas
(quem é champion, quem está perdido, etc.) são determinísticas.

Uso:
    python -X utf8 seed_demo.py --comercial   # gera data/demo_comercial.json
    python -X utf8 seed_demo.py --logistica   # gera data/demo.sqlite
    python -X utf8 seed_demo.py --all
"""
import sys
import json
import random
import sqlite3
from pathlib import Path
from datetime import date, timedelta

BASE = Path(__file__).resolve().parent
COMERCIAL_JSON = BASE / 'demo_comercial.json'
DEMO_SQLITE = BASE / 'demo.sqlite'

RNG = random.Random(42)
HOJE = date.today()

# ───────────────────────── pools fictícios ─────────────────────────
SUPERVISORES = {
    10: 'Equipe Triângulo',
    11: 'Equipe Capital',
    12: 'Equipe Litoral',
    13: 'Equipe Serra',
    14: 'Equipe Interior',
}

CIDADES = [
    ('Uberlândia', 'MG'), ('Uberaba', 'MG'), ('Belo Horizonte', 'MG'),
    ('Araguari', 'MG'), ('Patos de Minas', 'MG'),
    ('São Paulo', 'SP'), ('Campinas', 'SP'), ('Ribeirão Preto', 'SP'),
    ('Goiânia', 'GO'), ('Anápolis', 'GO'), ('Catalão', 'GO'),
    ('Vitória', 'ES'), ('Vila Velha', 'ES'), ('Cariacica', 'ES'),
    ('Rio de Janeiro', 'RJ'), ('Campos dos Goytacazes', 'RJ'),
]

DEPTOS = {
    1: 'Material de Limpeza', 2: 'Alimentícios', 3: 'Bebidas',
    4: 'Embalagens', 5: 'Higiene Pessoal', 6: 'Descartáveis',
    7: 'Bazar', 8: 'Pet', 9: 'Bobinas e Sacolas',
    10: 'Conservas', 11: 'Matinais', 12: 'Limpeza Industrial',
}

FORNECEDORES = [
    'Bril Higiene SA', 'Predileta Alimentos', 'Galvano Embalagens',
    'CristalCopo Descartáveis', 'HiperRoll Bobinas', 'NutriMais Conservas',
    'AromaCare Higiene', 'PetVida Nutrição', 'SoftPack Plásticos',
    'Aurora Bebidas', 'Campo Verde Matinais', 'IndClean Profissional',
]

# Bases de produto por departamento (grão do Radar). Combinadas com marca+tamanho
# geram um catálogo determinístico de ~180 SKUs fictícios.
PROD_BASE = {
    1:  ['Detergente', 'Desinfetante', 'Água Sanitária', 'Sabão em Pó', 'Multiuso', 'Amaciante'],
    2:  ['Arroz', 'Feijão', 'Açúcar', 'Óleo de Soja', 'Macarrão', 'Farinha'],
    3:  ['Refrigerante', 'Suco', 'Água Mineral', 'Energético', 'Néctar', 'Isotônico'],
    4:  ['Caixa Papelão', 'Filme Stretch', 'Fita Adesiva', 'Saco Kraft', 'Bandeja', 'Pote PP'],
    5:  ['Sabonete', 'Shampoo', 'Creme Dental', 'Papel Higiênico', 'Desodorante', 'Condicionador'],
    6:  ['Copo Descartável', 'Prato Descartável', 'Talher Plástico', 'Guardanapo', 'Marmitex', 'Canudo'],
    7:  ['Vassoura', 'Balde', 'Pano de Chão', 'Rodo', 'Esponja', 'Luva'],
    8:  ['Ração Cão', 'Ração Gato', 'Areia Higiênica', 'Petisco', 'Shampoo Pet', 'Tapete Higiênico'],
    9:  ['Bobina Picotada', 'Sacola Alça', 'Saco Lixo', 'Bobina Kraft', 'Saco Freezer', 'Filme PVC'],
    10: ['Milho Verde', 'Ervilha', 'Sardinha', 'Atum', 'Seleta Legumes', 'Molho de Tomate'],
    11: ['Café', 'Achocolatado', 'Biscoito', 'Leite em Pó', 'Cereal', 'Aveia'],
    12: ['Detergente Industrial', 'Desengraxante', 'Álcool 70', 'Cloro Ativo', 'Limpa Piso', 'Sabão de Coco'],
}
MARCAS_PROD = ['Prime', 'Max', 'Gold', 'Popular', 'Extra', 'Super', 'Nobre', 'Real']
TAM_PROD = ['500ml', '1L', '2L', '5L', '1kg', '2kg', '5kg', 'fardo', 'pct 12', 'cx 24']

PRE_NOMES = ['Comercial', 'Distribuidora', 'Mercado', 'Atacado', 'Supermercado',
             'Armazém', 'Empório', 'Casa', 'Depósito', 'Mini Mercado']
SOBRE_NOMES = ['Aliança', 'Progresso', 'União', 'Estrela', 'Boa Compra', 'Central',
               'Popular', 'Vitória', 'Bom Preço', 'Família', 'Real', 'Primor',
               'Esperança', 'Ouro Verde', 'São Jorge', 'Bandeirante', 'Triângulo',
               'Horizonte', 'Líder', 'Avenida', 'Cidade', 'Sol Nascente']
SUFIXOS = ['Ltda.', 'ME', 'EIRELI', 'Comércio Ltda.', 'e Cia']

NOMES_VEND = [
    'Ana Prado', 'Bruno Lima', 'Carla Dias', 'Diego Souza', 'Elaine Castro',
    'Fábio Reis', 'Gisele Moura', 'Heitor Nunes', 'Isadora Pires', 'João Vidal',
    'Karina Lopes', 'Lucas Teixeira', 'Marina Couto', 'Natan Rocha', 'Olívia Faria',
    'Pedro Antunes', 'Queila Barros', 'Rafael Mendes', 'Sabrina Goulart', 'Tiago Brandão',
    'Úrsula Campos', 'Vitor Hugo', 'Wagner Lessa', 'Xênia Almeida', 'Yuri Caldas',
]

# ─────────────── arquétipos de segmento (guias de geração) ───────────────
# (peso, recencia_dias, freq_ano, ticket_medio)
ARQ = [
    ('champions',           0.08, (1, 10),    (20, 42), (1800, 4200)),
    ('loyal',               0.16, (5, 25),    (12, 26), (1200, 2600)),
    ('potential_loyalist',  0.15, (3, 20),    (2, 6),   (700, 1600)),
    ('new',                 0.05, (1, 12),    (1, 2),   (500, 1400)),
    ('at_risk',             0.12, (40, 90),   (8, 18),  (1100, 2400)),
    ('cant_lose',           0.06, (55, 115),  (10, 22), (1900, 3800)),
    ('hibernating',         0.18, (95, 185),  (2, 6),   (500, 1300)),
    ('lost',                0.20, (190, 560), (1, 3),   (300, 900)),
]

# sazonalidade mensal (índice 1=jan): pico fim de ano
SAZON = {1: 0.88, 2: 0.86, 3: 0.95, 4: 0.97, 5: 1.0, 6: 0.98,
         7: 1.02, 8: 1.05, 9: 1.06, 10: 1.10, 11: 1.18, 12: 1.22}
CRESCIMENTO_ANUAL = 0.18  # YoY ~ +18%
MARGEM = 0.185


def _razao_social(i):
    pre = RNG.choice(PRE_NOMES)
    sob = RNG.choice(SOBRE_NOMES)
    suf = RNG.choice(SUFIXOS)
    return f"{pre} {sob} {suf}", f"{sob}"


def _telefone():
    ddd = RNG.choice([34, 31, 11, 19, 62, 27, 21])
    return f"({ddd}) 9{RNG.randint(1000,9999)}-{RNG.randint(1000,9999)}"


def _anomes(d):
    return d.strftime('%Y-%m')


def _fator_temporal(d):
    """Sazonalidade × crescimento (meses mais antigos valem menos → YoY positivo)."""
    meses_atras = (HOJE.year - d.year) * 12 + (HOJE.month - d.month)
    anos = meses_atras / 12.0
    return SAZON[d.month] * ((1 + CRESCIMENTO_ANUAL) ** (-anos))


def gerar_comercial(n_clientes=720):
    # vendedores: codusur 100..124, supervisor por banda de 5
    vendedores = []
    for idx in range(25):
        codusur = 100 + idx
        sup = 10 + (idx // 5)  # 100-104→10, 105-109→11 (inclui 107), ...
        tipo = 'I' if idx % 9 == 0 else 'R'
        cid, uf = RNG.choice(CIDADES)
        vendedores.append({
            'codusur': codusur, 'nome': NOMES_VEND[idx], 'tipo': tipo,
            'codsupervisor': sup, 'cidade': cid, 'estado': uf, 'bloqueio': 'N',
        })

    # fornecedores (codfornec 200..) — precisam existir antes do catálogo de produtos
    fornecedores = [{'codfornec': 200 + i, 'nome': n} for i, n in enumerate(FORNECEDORES)]
    fornec_nome_por_cod = {f['codfornec']: f['nome'] for f in fornecedores}
    fornec_cods = list(fornec_nome_por_cod)

    # catálogo de produtos (determinístico) — grão do Radar
    produtos = []
    produtos_por_depto = {}
    codprod = 5000
    for codepto in DEPTOS:
        for base in PROD_BASE.get(codepto, [DEPTOS[codepto]]):
            for _ in range(RNG.randint(2, 3)):
                cf = RNG.choice(fornec_cods)
                produtos.append({
                    'codprod': codprod,
                    'descricao': f"{base} {RNG.choice(MARCAS_PROD)} {RNG.choice(TAM_PROD)}",
                    'codepto': codepto,
                    'codfornec': cf,
                    'fornec_nome': fornec_nome_por_cod[cf],
                })
                produtos_por_depto.setdefault(codepto, []).append(codprod)
                codprod += 1

    pesos = [a[1] for a in ARQ]
    clientes = []
    for i in range(n_clientes):
        codcli = 1000 + i
        razao, fantasia = _razao_social(i)
        cid, uf = RNG.choice(CIDADES)
        vend = RNG.choice(vendedores)
        arq = RNG.choices(ARQ, weights=pesos, k=1)[0]
        nome_arq, _, rec_rng, freq_rng, tick_rng = arq

        recencia = RNG.randint(*rec_rng)
        freq_ano = RNG.randint(*freq_rng)
        ticket = RNG.uniform(*tick_rng)

        ultima = HOJE - timedelta(days=recencia)
        # intervalo médio entre compras
        intervalo = max(7, int(365 / max(1, freq_ano)))
        # quantos meses de histórico (clientes antigos têm mais → cohort profundo)
        historico_dias = RNG.choice([240, 360, 540, 720])
        datas = []
        d = ultima
        while d > HOJE - timedelta(days=historico_dias):
            datas.append(d)
            jitter = RNG.randint(-4, 8)
            d = d - timedelta(days=max(5, intervalo + jitter))
        datas.sort()

        mensal = {}
        deptos_cli = {}
        produtos_cli = {}
        for dt in datas:
            base_val = ticket * RNG.uniform(0.6, 1.5) * _fator_temporal(dt)
            venda = round(base_val, 2)
            lucro = round(venda * MARGEM * RNG.uniform(0.7, 1.3), 2)
            am = _anomes(dt)
            mm = mensal.setdefault(am, {'venda': 0.0, 'lucro': 0.0})
            mm['venda'] += venda
            mm['lucro'] += lucro
            # mix de departamentos (1-3 por compra)
            for cod in RNG.sample(list(DEPTOS), k=RNG.randint(1, 3)):
                dd = deptos_cli.setdefault(cod, {'venda': 0.0, 'lucro': 0.0})
                share = venda / 2
                dd['venda'] += round(share, 2)
                dd['lucro'] += round(share * MARGEM, 2)
                # produtos do depto nesta compra (1-2 SKUs) — grão do Radar.
                # Rateia a fatia do depto entre os SKUs; guarda evento (data, venda, qt).
                skus = produtos_por_depto.get(cod, [])
                if skus:
                    escolhidos = RNG.sample(skus, k=min(len(skus), RNG.randint(1, 2)))
                    vshare = share / len(escolhidos)
                    for cp in escolhidos:
                        qt = max(1, int(vshare / RNG.uniform(12, 60)))
                        produtos_cli.setdefault(cp, []).append(
                            [dt.isoformat(), round(vshare, 2), qt])

        # snapshot derivado (janela 12m)
        corte12 = HOJE - timedelta(days=365)
        datas12 = [dt for dt in datas if dt >= corte12]
        venda12 = round(sum(v['venda'] for am, v in mensal.items()
                            if date.fromisoformat(am + '-01') >= corte12.replace(day=1)), 2)
        lucro12 = round(sum(v['lucro'] for am, v in mensal.items()
                            if date.fromisoformat(am + '-01') >= corte12.replace(day=1)), 2)
        snapshot = {
            'DiasSemComprar': recencia,
            'Compras12m': len(datas12),
            'Lucro12m': lucro12,
            'Venda12m': venda12,
            'UltimaCompra': ultima.isoformat(),
        }

        clientes.append({
            'codcli': codcli,
            'cliente': razao,
            'fantasia': fantasia,
            'cidade': cid,
            'uf': uf,
            'codusur1': vend['codusur'],
            'telefone': _telefone(),
            'bloqueio': 'S' if RNG.random() < 0.03 else 'N',
            'arquetipo': nome_arq,
            'snapshot': snapshot,
            'datas': [dt.isoformat() for dt in datas],
            'mensal': {am: {'venda': round(v['venda'], 2), 'lucro': round(v['lucro'], 2)}
                       for am, v in sorted(mensal.items())},
            'deptos': {str(c): {'venda': round(v['venda'], 2), 'lucro': round(v['lucro'], 2)}
                       for c, v in deptos_cli.items()},
            'produtos': {str(cp): ev for cp, ev in produtos_cli.items()},
        })

    # série agregada 24m
    serie = {}
    for c in clientes:
        for am, v in c['mensal'].items():
            s = serie.setdefault(am, {'VendaLiquida': 0.0, 'LucroTotal': 0.0, 'clientes': set()})
            s['VendaLiquida'] += v['venda']
            s['LucroTotal'] += v['lucro']
            s['clientes'].add(c['codcli'])
    corte24 = (HOJE.replace(day=1) - timedelta(days=365 * 2))
    serie_agregada = []
    for am in sorted(serie):
        if date.fromisoformat(am + '-01') < corte24:
            continue
        s = serie[am]
        serie_agregada.append({
            'AnoMes': am,
            'VendaLiquida': round(s['VendaLiquida'], 2),
            'LucroTotal': round(s['LucroTotal'], 2),
            'ClientesUnicos': len(s['clientes']),
        })

    # A meta de cada métrica é derivada em tempo de request (mesmo mês do ano anterior ×
    # crescimento, medida no grão certo) por comercial/loaders_demo.py — o mês de
    # referência é o corrente. Aqui só ancoramos esse mês.
    out = {
        'gerado_em': HOJE.isoformat(),
        'anchor': HOJE.isoformat(),
        'empresa': 'Distribuidora Exemplo Ltda.',
        'supervisores': {str(k): v for k, v in SUPERVISORES.items()},
        'vendedores': vendedores,
        'deptos': {str(k): v for k, v in DEPTOS.items()},
        'fornecedores': fornecedores,
        'produtos': produtos,
        'clientes': clientes,
        'serie_agregada': serie_agregada,
        'metas_mes': HOJE.strftime('%Y-%m'),
    }
    COMERCIAL_JSON.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f"[comercial] {len(clientes)} clientes, {len(vendedores)} vendedores, "
          f"{len(produtos)} produtos, {len(serie_agregada)} meses → {COMERCIAL_JSON.name}")


# ───────────────────────── logística (SQLite) ─────────────────────────
def gerar_logistica():
    from seed_logistica import gerar  # módulo irmão (Onda 3)
    gerar(DEMO_SQLITE, RNG, HOJE)


def main():
    args = sys.argv[1:]
    if not args or '--all' in args:
        gerar_comercial()
        try:
            gerar_logistica()
        except Exception as e:  # logística ainda pode não existir
            print(f"[logistica] pulado: {e}")
        return
    if '--comercial' in args:
        gerar_comercial()
    if '--logistica' in args:
        gerar_logistica()


if __name__ == '__main__':
    main()
