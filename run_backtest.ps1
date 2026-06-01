# ============================================================
#  Запуск БЭКТЕСТА (прогон стратегии на истории)
#  Использование:   .\run_backtest.ps1
#  Меняй --timerange под нужный период (формат ГГГГММДД-ГГГГММДД)
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"

& ".\.venv\Scripts\freqtrade.exe" backtesting `
    --config "user_data\config.json" `
    --userdir "user_data" `
    --strategy "AtrTrendStrategy" `
    --timeframe "1h" `
    --timerange "20240601-20260601" `
    --cache none `
    --breakdown month
