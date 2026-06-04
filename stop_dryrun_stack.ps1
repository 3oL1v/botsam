$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$ports = @(8081, 8082, 8083, 8092)
$connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }
$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {
    try {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped process pid=$processId" -ForegroundColor Green
    } catch {
        Write-Host "Could not stop pid=${processId}: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "Stopped cloudflared pid=$($_.Id)" -ForegroundColor Green
}
