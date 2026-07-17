# JOGA Soluções Empresariais — Portfólio (demo)

App de demonstração para apresentar ao vivo a prospects. **Dados 100% fictícios**,
**sem dependências externas** (sem Power BI, sem APIs, sem banco obrigatório).

Dois módulos num app só:
- **JOGA Comercial** (`/comercial`) — Dashboard, Carteira RFM, Vendedores, Cockpit, Categorias, Mix abandonado, Tendências/Cohort, **Radar de Produtos**, **Metas** (4 métricas) e **Gerencial** (cobertura de carteira).
- **JOGA Operações** (`/operacoes`) — DRE financeiro, Embarques, Mapa de rastreamento.

## Rodar localmente (Windows)

```powershell
# 1. gerar a base sintética (1x; gera data/demo_comercial.json + data/demo.sqlite)
python -X utf8 data\seed_demo.py --all

# 2. subir o app
python -X utf8 app.py
#  → http://localhost:5000
```

Ou use o atalho: dê duplo-clique em **`run_demo.bat`**.

## Login (seletor de papel — 1 clique)

A tela de login mostra 4 perfis. Cada um enxerga um escopo de dados diferente
(controle de acesso real, ótimo pra demonstrar ao cliente):

| Perfil | Vê |
|---|---|
| **Diretor** | tudo (visão executiva) |
| **Supervisor** | só o time dele (Equipe Capital) |
| **Vendedor** | só a própria carteira |
| **Visitante** | leitura geral |

## Testes

```powershell
python -X utf8 -m pytest -q     # 54 testes (RFM, cohort, smoke, RBAC)
```

## Estrutura

```
app.py              # app Flask + blueprints + login/landing
config.py           # flags e caminhos
shared/             # auth (login demo + RBAC), cache em memória, db (sqlite/postgres)
comercial/          # módulo analytics: rfm.py, cohort.py, loaders_demo.py, routes.py, templates/
operacoes/          # módulo logística: data.py, dre_demo.py, routes.py, templates/
static/theme.css    # design system (dark + sidebar, âmbar/teal, Space Grotesk)
templates/          # _shell.html, login.html, landing.html
data/seed_demo.py   # gerador de dados sintéticos
tests/              # pytest
```

## Notas

- A base é regenerável e determinística (RNG com seed fixa); as datas são ancoradas
  em "hoje", então a demo sempre parece atual.
- Cache em memória (sem Redis). Em produção, Postgres é opcional (setar `DB_HOST`).
