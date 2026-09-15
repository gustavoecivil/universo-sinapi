# 📦 Guia de Instalação - Python e Dependências

## Opção 1: Instalar Python via Microsoft Store (Recomendado - Mais Fácil)

1. Abra a **Microsoft Store** no Windows
2. Procure por **"Python 3.12"** ou **"Python 3.11"**
3. Clique em **"Instalar"**
4. Aguarde a instalação concluir
5. Feche e reabra o terminal/PowerShell
6. Verifique a instalação:
   ```powershell
   python --version
   pip --version
   ```

## Opção 2: Instalar Python via Site Oficial (Mais Controle)

1. Acesse: https://www.python.org/downloads/
2. Baixe a versão mais recente do Python (3.11 ou 3.12)
3. **IMPORTANTE**: Durante a instalação, marque a opção **"Add Python to PATH"**
4. Escolha **"Install Now"** ou **"Customize installation"**
5. Se escolher customizar, certifique-se de marcar:
   - ✅ pip
   - ✅ tcl/tk and IDLE
   - ✅ Python test suite
   - ✅ py launcher
   - ✅ for all users (opcional)
6. Complete a instalação
7. Feche e reabra o terminal/PowerShell
8. Verifique a instalação:
   ```powershell
   python --version
   pip --version
   ```

## Opção 3: Usar Chocolatey (Se já tiver instalado)

Se você já tem o Chocolatey instalado:
```powershell
choco install python
```

## Após Instalar Python

### 1. Verificar Instalação
```powershell
python --version
pip --version
```

### 2. Atualizar pip (recomendado)
```powershell
python -m pip install --upgrade pip
```

### 3. Instalar Dependências do Projeto
Navegue até a pasta do projeto e execute:
```powershell
cd "C:\Users\Eduardo\Documents\Dev\Easy SINAPI ETL"
pip install -r requirements.txt
```

### 4. Verificar Instalação das Dependências
```powershell
pip list
```

Você deve ver:
- pandas
- openpyxl
- requests
- pyarrow
- python-dateutil

## Solução de Problemas

### Python não é reconhecido após instalação
1. Verifique se marcou "Add Python to PATH" durante a instalação
2. Se não marcou, reinstale o Python marcando essa opção
3. Ou adicione manualmente ao PATH:
   - Procure por "Variáveis de Ambiente" no Windows
   - Adicione o caminho do Python (geralmente `C:\Users\SeuUsuario\AppData\Local\Programs\Python\Python3XX`)
   - Adicione também a pasta Scripts (`C:\Users\SeuUsuario\AppData\Local\Programs\Python\Python3XX\Scripts`)

### pip não é reconhecido
1. Tente usar: `python -m pip` em vez de apenas `pip`
2. Verifique se pip está instalado: `python -m ensurepip --upgrade`

### Erro de permissão ao instalar pacotes
Use a flag `--user`:
```powershell
pip install --user -r requirements.txt
```

## Teste Rápido

Após instalar tudo, teste se está funcionando:
```powershell
python -c "import pandas; print('Pandas instalado com sucesso!')"
python -c "import requests; print('Requests instalado com sucesso!')"
```

## Próximos Passos

Após instalar Python e as dependências, você pode:

1. **Testar com arquivos existentes:**
   ```powershell
   python example_usage.py 5
   ```

2. **Executar o ETL completo:**
   ```powershell
   python main.py --year 2025 --month 12
   ```

3. **Ver ajuda do script principal:**
   ```powershell
   python main.py --help
   ```
