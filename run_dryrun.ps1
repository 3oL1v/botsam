# ============================================================
#  Запуск Freqtrade в режиме DRY-RUN (бумажная торговля)
#  Двойной клик не нужен: открой PowerShell в папке C:\trade2
#  и выполни:   .\run_dryrun.ps1
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# UTF-8, чтобы корректно печатались таблицы и логи
$env:PYTHONUTF8 = "1"

# Загружаем переменные из .env (ключи биржи и пр.), пропуская комментарии
if (Test-Path ".\.env") {
    Get-Content ".\.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $name = $line.Substring(0, $idx).Trim()
            $value = $line.Substring($idx + 1).Trim()
            Set-Item -Path ("Env:" + $name) -Value $value
        }
    }
    Write-Host "[.env загружен]" -ForegroundColor Green
}

# Запуск бота. dry_run=true задан в config.json (реальные деньги НЕ задействованы).
& ".\.venv\Scripts\freqtrade.exe" trade `
    --config "user_data\config.json" `
    --userdir "user_data" `
    --strategy "AtrTrendStrategy"
