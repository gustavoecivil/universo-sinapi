# Script PowerShell para instalar dependências após Python estar instalado
# Execute este script após instalar o Python

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Instalação de Dependências - SINAPI ETL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se Python está instalado
Write-Host "Verificando instalação do Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python não encontrado!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor, instale o Python primeiro:" -ForegroundColor Yellow
    Write-Host "1. Acesse: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "2. Baixe e instale o Python" -ForegroundColor Yellow
    Write-Host "3. IMPORTANTE: Marque 'Add Python to PATH' durante a instalação" -ForegroundColor Yellow
    Write-Host "4. Execute este script novamente após instalar" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Verificar se pip está disponível
Write-Host "Verificando instalação do pip..." -ForegroundColor Yellow
try {
    $pipVersion = pip --version 2>&1
    Write-Host "✅ pip encontrado: $pipVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️ pip não encontrado, tentando instalar..." -ForegroundColor Yellow
    python -m ensurepip --upgrade
}

Write-Host ""

# Atualizar pip
Write-Host "Atualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "✅ pip atualizado" -ForegroundColor Green

Write-Host ""

# Verificar se requirements.txt existe
if (-not (Test-Path "requirements.txt")) {
    Write-Host "❌ Arquivo requirements.txt não encontrado!" -ForegroundColor Red
    exit 1
}

# Instalar dependências
Write-Host "Instalando dependências do projeto..." -ForegroundColor Yellow
Write-Host ""

python -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✅ Instalação concluída com sucesso!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Você pode agora executar:" -ForegroundColor Cyan
    Write-Host "  python example_usage.py 5" -ForegroundColor White
    Write-Host "  python main.py --help" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Erro ao instalar dependências" -ForegroundColor Red
    Write-Host "Tente executar manualmente: pip install -r requirements.txt" -ForegroundColor Yellow
}
