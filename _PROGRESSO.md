# JOGA Portfólio — Progresso

App de portfólio demo (dados fictícios, sem dependências externas) combinando
dois módulos. Plano-pai: ver `C:\Users\note\.claude\plans\na-verdade-diferente-to-wobbly-dolphin.md`.

## Status das ondas

| Onda | Entrega | Status |
|---|---|---|
| 0 | Esqueleto: `app.py` (2 blueprints), `config.py`, `shared/auth.py` (login demo + RBAC), `shared/cache.py` (memória), `shared/db.py` (sqlite/postgres) | ✅ |
| 1 | `data/seed_demo.py` (720 clientes, 25 vendedores, série 24m) + `data/seed_logistica.py` (40 cargas + DRE 12m em SQLite) | ✅ |
| 2 | Módulo **Comercial** — `rfm.py`/`cohort.py` (copiados verbatim), `loaders_demo.py`, `routes.py`, 7 telas | ✅ testado |
| 3 | Módulo **Operações** — `data.py`, `dre_demo.py`, `routes.py`, telas DRE/Embarques/Mapa (Leaflet) | ✅ testado |
| 4 | Tema `static/theme.css` (dark grafite + âmbar/teal, Space Grotesk, sidebar) + `_shell.html` | ✅ |
| 5 | Login seletor de papel + landing com switch de módulo | ✅ |
| 6 | `pytest` (54 testes: RFM, cohort, smoke, RBAC), `requirements.txt`, README, launcher | ✅ |
| 7 | **Deploy** (Dockerfile, compose, Traefik subdomínio) | ⏳ **aguardando teste do usuário** |

## Validação E2E (resultados reais)

- **RBAC**: diretor vê 720 clientes, supervisor 146, vendedor 27. Ranking bloqueado p/ vendedor (403); cockpit de outro vendedor bloqueado (403); supervisor não vê vendedor de outro time (403).
- **Dashboard comercial**: 8 KPIs, série 24m com sazonalidade, YoY, top-clientes, donut de segmentos.
- **Carteira RFM**: 8 segmentos não-zero (distribuição orgânica via lógica real); filtros (vendedor/UF/segmento/busca), drill 360°, export CSV.
- **DRE**: receita R$18,5M, resultado R$4,8M, margem 25,7%, detalhamento por grupo/evento.
- **Mapa**: 16 cargas em rota com posição/rota (Leaflet + tiles CARTO dark).
- **pytest**: 54/54 verdes em ~0,7s.
- Boot real do servidor (`python app.py`) responde HTTP; APIs bloqueiam sem sessão (401), páginas redirecionam p/ login.

## Patch pós-teste — DRE contábil completo (2ª rodada)

Feedback do usuário: o DRE não era um DRE de verdade (só somava despesas em 3 grupos genéricos).
Refeito com a **estrutura contábil obrigatória** (espelha `DRE_LINHAS` do Tabela Auditoria):

- `data/seed_logistica.py` — tabela `dre_mensal` agora tem `(anomes, tipo, grupo, subgrupo, evento, valor)`;
  `DRE_EVENTOS` (~31 eventos) mapeados nos 7 grupos da cascata com proporções realistas de transporte.
- `operacoes/dre_demo.py` — `calcular()` monta a cascata de 14 linhas (Receita Bruta → Deduções →
  Receita Líquida → Custo Op. → Desp. Adm. → EBITDA → Financeiras → LAIR → Impostos → Lucro Líquido →
  Investimentos → Pós-Investimento → Retiradas → Resultado Final) + drill grupo→subgrupo→evento + série mensal.
- `operacoes/templates/operacoes/dre.html` — 6 KPIs, gráfico **cascata (waterfall)**, série mensal
  (receita×EBITDA×resultado) e **tabela em cascata com linhas de grupo expansíveis** (drill).
- `tests/test_dre.py` — 6 testes (cascata fecha, 14 linhas, soma eventos = grupo, custo op. é o maior, margem final realista, série 12m).

Resultado E2E: Receita R$18,3M · EBITDA 13,6% · Lucro Líquido 7,6% · **Resultado Final 3,0%**. **60/60 testes verdes.**

## Patch — Comercial completo (3 abas do Multpel replicadas)

Objetivo: fechar a defasagem entre a navegação do Multpel (11 abas) e a do JOGA (7),
replicando **Metas, Gerencial (Cobertura) e Radar de Produtos** (Admin descartada — toca auth
real, pouco útil na demo). Telas próprias, sobre o dataset sintético, reusando os módulos puros.

- **Seed estendido** (`data/seed_demo.py`): catálogo de **181 produtos** (`produtos`) + histórico
  por SKU em cada cliente (`clientes[].produtos = {codprod: [[iso, venda, qt], ...]}`) — grão do
  Radar. Determinístico (RNG 42, sem alterar os draws antigos). `metas_mes` ancora o mês de referência.
- **Gerencial** (`comercial/cobertura.py` portado verbatim + `cobertura_niveis` + `/gerencial`):
  placar Empresa→Time→Vendedor de % em dia (≤ janela), faixas de recência, receita em risco, alerta
  de limiar. E2E: empresa 46,7% cobertura, base morta 281, faixas somam 720.
- **Radar** (`comercial/radar.py` puro + loaders + `/radar`): produtos sangrando (janela recente ×
  anterior), drill por produto → clientes parou/perdido/esfriando + troca-vs-abandono. E2E: 110
  produtos sangrando @60d; drill do top com status coerente.
- **Metas** (`comercial/metas.py` copiado + loaders + `/metas`): 4 métricas (Venda/Rentab/Clientes/Mix)
  meta × realizado × projeção/necessidade em **dias úteis**, drill de vendedores, série diária.
  **Meta calculada no grão certo** (mesmo mês do ano anterior × crescimento, distinct-aware p/
  clientes/mix) — evita estourar o DISTINCTCOUNT no rollup. E2E: 4 métricas ~96–103% no total.
- **Nav** (`_shell.html`): + Radar, Metas, Gerencial (sob `/comercial/*`).
- **Testes**: +31 (test_cobertura/test_metas/test_radar + smoke/RBAC das 3 abas). **91/91 verdes.**
- **RBAC** validado ao vivo: Gerencial 720→164→33, Metas 5→1→1 times, Radar 110→90→64;
  drill de metas de time alheio → 403.

## Decisões / desvios

1. **Telas novas (não reaproveitamento 1:1 dos frontends originais)** — para máxima confiabilidade ao vivo e identidade visual própria. O Multpel (sem contrato) inspirou a lógica; o Tabela Auditoria (com contrato) NÃO teve código/visual copiado — a logística é toda sintética e com telas próprias.
2. **Comercial = JSON sintético** (sem banco). **Logística = SQLite** semeado (sem Postgres pra rodar local). Postgres só se `DB_HOST` setado (caminho de prod).
3. **Cache em memória** (dict com TTL) no lugar do Redis.
4. **Login = seletor de papel** (sem banco de senhas). Os 4 papéis exercitam o RBAC real.
5. Dados determinísticos (seed 42) mas datas ancoradas em "hoje" → demo sempre atual.

## Como rodar / testar (para o usuário validar antes da Onda 7)

```powershell
cd "c:\Phyton-Projetos\JOGA Portfolio"
python -X utf8 data\seed_demo.py --all     # 1x
python -X utf8 app.py                       # http://localhost:5000
python -X utf8 -m pytest -q                 # 54 verdes
```
Login: escolher Diretor / Supervisor / Vendedor / Visitante.

## Pendências / ideias pós-teste

- **Onda 7 — Deploy**: Dockerfile (python:3.11-slim, gunicorn), docker-compose, labels Traefik p/ subdomínio (espelhar Tabela Auditoria). Seed roda no build.
- Eventual tela "Novo embarque" (form) se quiser CRUD na demo.
- Pré-empacotar Chart.js/Leaflet local em `static/` se a demo precisar rodar 100% offline (hoje vêm de CDN).
- Ajustar marca/cores se quiser afinar a identidade visual.
