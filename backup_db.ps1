Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Automated PostgreSQL Database Backup    " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "ai_sales_crm_${timestamp}.sql.gz"
$localBackupDir = Join-Path $PSScriptRoot "backups"

if (-not (Test-Path $localBackupDir)) {
    New-Item -ItemType Directory -Path $localBackupDir -Force | Out-Null
}

Write-Host "`n1. Creating database dump on therealbonz.com..." -ForegroundColor Yellow
$remoteCmd = "mkdir -p /home/bonz/backups && pg_dump -U bonz ai_sales_crm | gzip > /home/bonz/backups/$backupFile"
ssh -o StrictHostKeyChecking=no bonz@therealbonz.com $remoteCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error generating backup on remote server. Aborting." -ForegroundColor Red
    exit 1
}

Write-Host "`n2. Downloading backup snapshot to local machine..." -ForegroundColor Yellow
$localFile = Join-Path $localBackupDir $backupFile
scp -o StrictHostKeyChecking=no bonz@therealbonz.com:/home/bonz/backups/$backupFile $localFile

if ($LASTEXITCODE -eq 0 -and (Test-Path $localFile)) {
    $size = (Get-Item $localFile).Length
    $sizeKb = [Math]::Round($size / 1024, 2)
    Write-Host "`n Backup Successfully Created & Archived!" -ForegroundColor Green
    Write-Host " Remote Path : /home/bonz/backups/$backupFile" -ForegroundColor Cyan
    Write-Host " Local Path  : $localFile ($sizeKb KB)" -ForegroundColor Cyan
    Write-Host "`nTo restore this backup at any time:" -ForegroundColor DarkYellow
    Write-Host " gunzip -c /home/bonz/backups/$backupFile | psql -U bonz ai_sales_crm" -ForegroundColor DarkGray
} else {
    Write-Host "Backup created on server but local SCP transfer encountered an issue." -ForegroundColor Yellow
}
