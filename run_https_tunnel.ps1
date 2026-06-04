$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$cloudflared = (Get-Command cloudflared -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

$existing = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $existing) {
    $p = Start-Process -FilePath $cloudflared `
        -ArgumentList @("tunnel","--url","http://127.0.0.1:8092") `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "logs\cloudflared.out.log" `
        -RedirectStandardError "logs\cloudflared.err.log" `
        -PassThru
    Write-Host "[cloudflared] started pid=$($p.Id)" -ForegroundColor Green
} else {
    Write-Host "[cloudflared] already running" -ForegroundColor Yellow
}

$url = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $log = @()
    if (Test-Path "logs\cloudflared.err.log") { $log += Get-Content "logs\cloudflared.err.log" }
    if (Test-Path "logs\cloudflared.out.log") { $log += Get-Content "logs\cloudflared.out.log" }
    $url = ($log | Select-String -Pattern "https://[-a-zA-Z0-9]+\.trycloudflare\.com" -AllMatches | ForEach-Object { $_.Matches.Value } | Select-Object -First 1)
    if ($url) { break }
}

$tokenLine = Get-Content ".\.env" -ErrorAction SilentlyContinue | Where-Object { $_ -like "MINIAPP_ACCESS_TOKEN=*" } | Select-Object -First 1
$token = if ($tokenLine) { $tokenLine.Split("=", 2)[1] } else { "" }

if ($url) {
    Write-Host ""
    Write-Host "HTTPS Mini App:" -ForegroundColor Cyan
    Write-Host "$url/miniapp?access=$token"
} else {
    Write-Host "Tunnel started, but URL was not found in logs yet. Check logs\cloudflared.err.log." -ForegroundColor Yellow
}
