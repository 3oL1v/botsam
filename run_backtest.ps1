$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"

$timerange = if ($args.Count -gt 0) { $args[0] } else { "20260101-20260604" }
$configs = @(
    "user_data\config_volatility_dry.json",
    "user_data\config_donchian_dry.json",
    "user_data\config_vwap_dry.json"
)

foreach ($config in $configs) {
    Write-Host ""
    Write-Host "[backtest] $config timerange=$timerange" -ForegroundColor Cyan
    & ".\.venv\Scripts\python.exe" -m freqtrade backtesting `
        --config $config `
        --userdir "user_data" `
        --timeframe "5m" `
        --timerange $timerange `
        --cache none `
        --breakdown day
}
