"""Configuração central do app de portfólio JOGA Soluções Empresariais.

Tudo roda em DEMO_MODE: sem Power BI, sem APIs externas, dados sintéticos.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'

# Demo sempre ligado neste projeto (é um portfólio, nunca toca dados reais).
DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() == 'true'

SECRET_KEY = os.getenv('SECRET_KEY', 'joga-demo-secret-troque-em-prod')

# Marca
MARCA = 'JOGA'
MARCA_FULL = 'JOGA Soluções Empresariais'
EMPRESA_EXEMPLO = 'Distribuidora Exemplo Ltda.'   # empresa fictícia dos dados

# Arquivos de dados sintéticos
COMERCIAL_JSON = DATA_DIR / 'demo_comercial.json'
MUNICIPIOS_JSON = DATA_DIR / 'municipios.json'
DEMO_SQLITE = DATA_DIR / 'demo.sqlite'

# Postgres opcional (logística). Se DB_HOST não setado, usa SQLite local.
USE_POSTGRES = bool(os.getenv('DB_HOST'))
