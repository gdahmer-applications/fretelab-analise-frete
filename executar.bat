@echo off
cd /d "%~dp0"

IF EXIST ".venv\Scripts\activate.bat" (
    echo Ativando ambiente virtual...
    call .venv\Scripts\activate
) ELSE (
    echo Virtualenv nao encontrado em ".venv". Usando ambiente do sistema.
)

echo Iniciando servidor local (Flask)...
echo Acesse: http://127.0.0.1:5000
python app.py
pause
