Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Deploying AI Sales Platform to Server   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "`n1. Pushing latest code to GitHub..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error pushing to GitHub. Aborting deployment." -ForegroundColor Red
    exit 1
}

Write-Host "`n2. Pulling latest code on therealbonz.com..." -ForegroundColor Yellow
ssh bonz@therealbonz.com "cd /home/bonz/JsProject && git fetch origin main && git reset --hard origin/main && pkill -u bonz -f uvicorn"

Write-Host "`n3. Waiting for server to reload..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $response = Invoke-RestMethod -Uri "https://therealbonz.com/JsProject/health" -UseBasicParsing
    Write-Host "`n Live Server Online!" -ForegroundColor Green
    Write-Host " Environment : $($response.environment)" -ForegroundColor Cyan
    Write-Host " Database    : $($response.database)" -ForegroundColor Cyan
    Write-Host " Status      : $($response.status)" -ForegroundColor Cyan
} catch {
    Write-Host "Note: Server is restarting. Check https://therealbonz.com/JsProject/health" -ForegroundColor DarkYellow
}

Write-Host "`n Deployment successfully completed!" -ForegroundColor Green
Write-Host " Dashboard: https://therealbonz.com/JsProject/console" -ForegroundColor Magenta
