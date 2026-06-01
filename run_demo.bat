@echo off
REM Atalho para rodar a demo JOGA localmente.
cd /d "%~dp0"
echo == Gerando base sintetica (se necessario) ==
if not exist "data\demo_comercial.json" python -X utf8 data\seed_demo.py --all
if not exist "data\demo.sqlite" python -X utf8 data\seed_demo.py --logistica
echo == Subindo o app em http://localhost:5000 ==
start "" http://localhost:5000
python -X utf8 app.py
