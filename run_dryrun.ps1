$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"

if (Test-Path ".\.env") {
    Get-Content ".\.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            Set-Item -Path ("Env:" + $line.Substring(0, $idx).Trim()) -Value $line.Substring($idx + 1).Trim()
        }
    }
}

New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

$services = @(
    @{Name="volatility"; Port=8081; Config="user_data\config_volatility_dry.json"; Log="logs\volatility.log"},
    @{Name="donchian";   Port=8082; Config="user_data\config_donchian_dry.json";   Log="logs\donchian.log"},
    @{Name="vwap";       Port=8083; Config="user_data\config_vwap_dry.json";       Log="logs\vwap.log"}
)

foreach ($svc in $services) {
    $listening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $svc.Port }
    if ($listening) {
        Write-Host "[$($svc.Name)] already listening on $($svc.Port)" -ForegroundColor Yellow
        continue
    }
    $p = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
        -ArgumentList @("-m","freqtrade","trade","--config",$svc.Config,"--userdir","user_data","--logfile",$svc.Log) `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "[$($svc.Name)] started pid=$($p.Id), port=$($svc.Port)" -ForegroundColor Green
}

$dashboardPort = 8092
$dashboardListening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $dashboardPort }
if (-not $dashboardListening) {
    $p = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
        -ArgumentList @("-m","uvicorn","dashboard.server:app","--host","127.0.0.1","--port","8092","--log-level","info") `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "logs\dashboard.out.log" `
        -RedirectStandardError "logs\dashboard.err.log" `
        -PassThru
    Write-Host "[dashboard] started pid=$($p.Id), port=8092" -ForegroundColor Green
} else {
    Write-Host "[dashboard] already listening on 8092" -ForegroundColor Yellow
}

$tokenLine = Get-Content ".\.env" -ErrorAction SilentlyContinue | Where-Object { $_ -like "MINIAPP_ACCESS_TOKEN=*" } | Select-Object -First 1
$token = if ($tokenLine) { $tokenLine.Split("=", 2)[1] } else { "" }
Write-Host ""
Write-Host "Local Mini App:" -ForegroundColor Cyan
Write-Host "http://127.0.0.1:8092/miniapp?access=$token"
Write-Host ""
Write-Host "Run .\run_https_tunnel.ps1 to create a temporary HTTPS URL."
