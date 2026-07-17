"""Motor de Cobertura de Carteira. Funções puras — sem Flask/DB.
Portado verbatim do Multpel (mesmo estilo de rfm.py / cohort.py); os campos de
cliente batem com o que rfm.calcular_clientes já produz no JOGA Portfolio.

Conceito:
- "Cobertura" = fatia da carteira que está EM DIA (última compra ≤ coberto_dias).
  É a mesma métrica em dois zooms: o índice % (placar) e a distribuição por faixa.
  Índice = clientes/valor na janela coberta ÷ total da carteira.

Camadas prontas em cada cliente (rfm.calcular_clientes):
- cobertura_ciclo: fração dentro do PRÓPRIO ciclo do cliente (ranking justo).
- receita_em_risco: Σ receita_perdida_proj (o "onde atuar" com cifrão).

Entrada: lista de clientes enriquecidos por rfm.py + vendedor/time
(cada dict tem recencia_dias, venda_12m, status_personalizada,
receita_perdida_proj, codusur, vendedor, codsupervisor, time).
"""
from datetime import datetime

# Faixas FIXAS (não mudam com o toggle de "coberto").
# (chave, limite_inferior, limite_superior) — inclusivos. 91+ tem topo aberto.
FAIXAS = [
    ('0-15',  0,  15),
    ('16-30', 16, 30),
    ('31-45', 31, 45),
    ('46-60', 46, 60),
    ('61-90', 61, 90),
    ('91+',   91, 10 ** 9),
]

COBERTO_DIAS_PADRAO = 30          # "em dia" default (linha 0-30 do diretor)
MIN_AMOSTRA = 5                   # abaixo disso o % é ruído → flag amostra_pequena
_STATUS_NO_CICLO = ('ok', 'normal')  # dentro do ciclo pessoal do cliente


def faixa_de(recencia_dias):
    """Mapeia dias-sem-comprar na chave da faixa. None/negativo → '91+' (sumido)."""
    if recencia_dias is None or recencia_dias < 0:
        return '91+'
    for chave, lo, hi in FAIXAS:
        if lo <= recencia_dias <= hi:
            return chave
    return '91+'


def _pct(parte, todo):
    """Divisão segura → 0.0 se denominador vazio."""
    return (parte / todo) if todo else 0.0


def agregar_grupo(clientes, coberto_dias=COBERTO_DIAS_PADRAO):
    """Agrega uma lista de clientes num placar de cobertura + distribuição por faixa."""
    total = len(clientes)
    valor_total = sum((c.get('venda_12m') or 0.0) for c in clientes)

    buckets_idx = {chave: {'clientes': 0, 'valor': 0.0} for chave, _, _ in FAIXAS}
    clientes_cobertos = 0
    valor_coberto = 0.0
    no_ciclo = 0
    receita_em_risco = 0.0
    for c in clientes:
        dias = c.get('recencia_dias')
        b = buckets_idx[faixa_de(dias)]
        v = c.get('venda_12m') or 0.0
        b['clientes'] += 1
        b['valor'] += v
        if dias is not None and dias >= 0 and dias <= coberto_dias:
            clientes_cobertos += 1
            valor_coberto += v
        if c.get('status_personalizada') in _STATUS_NO_CICLO:
            no_ciclo += 1
        receita_em_risco += (c.get('receita_perdida_proj') or 0.0)

    buckets = [{
        'faixa':        chave,
        'clientes':     buckets_idx[chave]['clientes'],
        'valor':        round(buckets_idx[chave]['valor'], 2),
        'pct_clientes': _pct(buckets_idx[chave]['clientes'], total),
        'pct_valor':    _pct(buckets_idx[chave]['valor'], valor_total),
    } for chave, _, _ in FAIXAS]

    # Rollup 0-30 = 0-15 + 16-30 (linha explícita do diretor, independente do toggle)
    c_0_30 = buckets_idx['0-15']['clientes'] + buckets_idx['16-30']['clientes']
    v_0_30 = buckets_idx['0-15']['valor'] + buckets_idx['16-30']['valor']
    rollup_0_30 = {
        'clientes':     c_0_30,
        'valor':        round(v_0_30, 2),
        'pct_clientes': _pct(c_0_30, total),
        'pct_valor':    _pct(v_0_30, valor_total),
    }

    return {
        'total_clientes':     total,
        'valor_total':        round(valor_total, 2),
        'media_mensal':       round(valor_total / 12, 2),
        'clientes_cobertos':  clientes_cobertos,
        'valor_coberto':      round(valor_coberto, 2),
        'cobertura_clientes': _pct(clientes_cobertos, total),
        'cobertura_valor':    _pct(valor_coberto, valor_total),
        'cobertura_ciclo':    _pct(no_ciclo, total),
        'receita_em_risco':   round(receita_em_risco, 2),
        'base_morta':         buckets_idx['91+']['clientes'],
        'buckets':            buckets,
        'rollup_0_30':        rollup_0_30,
    }


def _agrupar_por(clientes, id_key, nome_key, sem_label, coberto_dias, extra_keys=()):
    """Agrupa por id_key (codsupervisor/codusur), monta placar por grupo, ordena pior→melhor.
    Clientes sem id caem num grupo id=None com rótulo `sem_label` (reconcilia com o total).
    `extra_keys`: campos copiados do 1º cliente pra cada grupo (ex.: codsupervisor no vendedor)."""
    grupos = {}
    for c in clientes:
        gid = c.get(id_key)
        bucket = grupos.setdefault(gid, {'clientes': [], 'nome': None})
        bucket['clientes'].append(c)
        if bucket['nome'] is None and c.get(nome_key):
            bucket['nome'] = c.get(nome_key)

    out = []
    for gid, bucket in grupos.items():
        agg = agregar_grupo(bucket['clientes'], coberto_dias)
        agg['id'] = gid
        agg['nome'] = bucket['nome'] or (sem_label if gid is None else f'#{gid}')
        agg['amostra_pequena'] = agg['total_clientes'] < MIN_AMOSTRA
        primeiro = bucket['clientes'][0]
        for k in extra_keys:
            agg[k] = primeiro.get(k)
        out.append(agg)

    # Pior→melhor por cobertura_clientes; empate → carteira maior primeiro (mais impacto).
    out.sort(key=lambda g: (g['cobertura_clientes'], -g['total_clientes']))
    return out


def agregar_niveis(clientes, coberto_dias=COBERTO_DIAS_PADRAO):
    """Placar completo em 3 níveis. Empresa reconcilia com a soma dos times/vendedores.
    Retorna {empresa, times[], vendedores[], coberto_dias, gerado_em}."""
    empresa = agregar_grupo(clientes, coberto_dias)
    times = _agrupar_por(clientes, 'codsupervisor', 'time', '(Sem time)', coberto_dias)
    vendedores = _agrupar_por(clientes, 'codusur', 'vendedor', '(Sem RCA)', coberto_dias,
                              extra_keys=('codsupervisor', 'time'))
    return {
        'empresa':      empresa,
        'times':        times,
        'vendedores':   vendedores,
        'coberto_dias': coberto_dias,
        'gerado_em':    datetime.now().isoformat(timespec='seconds'),
    }


def times_rcas_abaixo(niveis, limiar_pct):
    """Filtra times e vendedores com cobertura_clientes < limiar (0..1) — base do alerta.
    limiar_pct em % (ex.: 60). Retorna {'times': [...], 'vendedores': [...]} pior→melhor."""
    lim = (limiar_pct or 0) / 100.0
    return {
        'times':      [t for t in niveis['times'] if t['cobertura_clientes'] < lim],
        'vendedores': [v for v in niveis['vendedores'] if v['cobertura_clientes'] < lim],
    }
