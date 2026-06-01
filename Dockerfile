FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gera a base sintética dentro da imagem (determinística) — comercial JSON + logística SQLite
RUN python -X utf8 data/seed_demo.py --all

EXPOSE 5000

# Servidor de produção (Gunicorn). app:app = objeto Flask em app.py
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "120", "app:app"]
