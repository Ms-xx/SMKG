# ============================================================================
#  start_all.ps1 - One-click launcher for the LX platform (per usingtest doc)
#  Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File .\start_all.ps1
#  Each service runs in its own PowerShell window; closing a window stops it.
#  Assumes: Redis/MySQL/Neo4j local services, LM Studio(qwen3-4b:1234) OPEN.
# ============================================================================

$ErrorActionPreference = "Continue"

# ---- configurable ----
$RootDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$PySciMKG     = "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe"
$PyGraph      = "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe"  # adjust if GraphRAGTest uses another env
$MinioExe     = "D:\workapp\MinIO\minio.exe"
$MinioDataDir = "D:\minio-data"

# ---- open a command in its own window ----
function Open-Node {
    param([string]$Title, [string]$WorkDir, [string]$Command)
    $inner = "& { [Console]::Title = '$Title'; Set-Location -LiteralPath '$WorkDir'; $Command }"
    Start-Process powershell -ArgumentList @(
        "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", $inner
    ) -WorkingDirectory $RootDir | Out-Null
    Write-Host "[start] $Title" -ForegroundColor Cyan
}

Write-Host "======== LX platform one-click start ========" -ForegroundColor Green
Write-Host "root: $RootDir"

# ---------- 1. databases ----------
# Redis
$rUp = Test-NetConnection 127.0.0.1 -Port 6379 -WarningAction SilentlyContinue
if (-not $rUp.TcpTestSucceeded) {
    Open-Node -Title "Redis" -WorkDir $RootDir -Command "Get-Command redis-server -ErrorAction SilentlyContinue | ForEach-Object { & $_.Source }"
} else {
    Write-Host "[OK] Redis 127.0.0.1:6379" -ForegroundColor Green
}

# MySQL (assume local service, WX db)
$mUp = Test-NetConnection 127.0.0.1 -Port 3306 -WarningAction SilentlyContinue
if ($mUp.TcpTestSucceeded) {
    Write-Host "[OK] MySQL 127.0.0.1:3306" -ForegroundColor Green
} else {
    Write-Host "[WARN] MySQL not listening on 3306 - start local MySQL service" -ForegroundColor Yellow
}

# Neo4j
$nUp = Test-NetConnection 127.0.0.1 -Port 7687 -WarningAction SilentlyContinue
if (-not $nUp.TcpTestSucceeded) {
    Open-Node -Title "Neo4j" -WorkDir $RootDir -Command "neo4j console"
} else {
    Write-Host "[OK] Neo4j bolt://127.0.0.1:7687" -ForegroundColor Green
}

# MinIO
$minUp = Test-NetConnection 127.0.0.1 -Port 9000 -WarningAction SilentlyContinue
if (-not $minUp.TcpTestSucceeded) {
    Open-Node -Title "MinIO" -WorkDir $RootDir -Command "& '$MinioExe' server '$MinioDataDir' --console-address ':9001'"
} else {
    Write-Host "[OK] MinIO 127.0.0.1:9000" -ForegroundColor Green
}

# ---------- 2. backend ----------
Open-Node -Title "Backend(uvicorn:8000)" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m uvicorn app.main:app --reload --port 8000"

Open-Node -Title "Celery Worker" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph"

Open-Node -Title "Celery Beat" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m celery -A app.core.celery_app beat -l info"

# ---------- 3. GraphRAGTest (needs LM Studio 1234 + Neo4j) ----------
Open-Node -Title "GraphRAGTest(8001)" -WorkDir "$RootDir\GraphRAGTest" -Command "& '$PyGraph' app.py"

# ---------- 5. frontend ----------
Open-Node -Title "Frontend(pnpm:3000)" -WorkDir "$RootDir\frontend" -Command "pnpm dev"

Write-Host ""
Write-Host "======== services launched, verify ========" -ForegroundColor Green
Write-Host "  backend      http://localhost:8000/health"
Write-Host "  API docs     http://localhost:8000/docs"
Write-Host "  GraphRAG     http://localhost:8001/docs"
Write-Host "  frontend     http://localhost:3000"
Write-Host "  login        admin / admin123"
Write-Host "  MinIO ui     http://localhost:9001"
Write-Host "==========================================="