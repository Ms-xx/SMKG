# ============================================================================
#  start_all.ps1 - One-click launcher for the LX platform
#  Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File .\start_all.ps1
#  Each app service runs in its own PowerShell window; closing a window stops it.
#  Redis / MySQL / Neo4j are expected as Windows local services (auto-start if
#  they are installed but stopped); MinIO is launched as a foreground process.
#  Prerequisites: LM Studio(qwen3-4b:1234) OPEN for GraphRAG/LLM features.
# ============================================================================

$ErrorActionPreference = "Continue"

# ---- configurable ----
$RootDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$PySciMKG     = "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe"
$PyGraph      = "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe"  # GraphRAGTest uses the same env
$MinioExe     = "D:\workapp\MinIO\minio.exe"
$MinioDataDir = "D:\minio-data"

# ---- sanity checks ----
$bad = @()
if (-not (Test-Path $PySciMKG))   { $bad += "SciMKG python ($PySciMKG)" }
if (-not (Test-Path "$RootDir\backend"))  { $bad += "backend dir" }
if (-not (Test-Path "$RootDir\GraphRAGTest")) { $bad += "GraphRAGTest dir" }
if (-not (Test-Path "$RootDir\frontend"))  { $bad += "frontend dir" }
if ($bad.Count -gt 0) {
    Write-Host "[FATAL] missing: $($bad -join ', ')" -ForegroundColor Red
    exit 1
}

# ---- helpers ----
function Test-Port([int]$Port) {
    return (Test-NetConnection 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
}

function Wait-Port([int]$Port, [int]$Seconds = 20) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Open-Node {
    param([string]$Title, [string]$WorkDir, [string]$Command)
    $inner = "& { [Console]::Title = '$Title'; Set-Location -LiteralPath '$WorkDir'; $Command }"
    Start-Process powershell -ArgumentList @(
        "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", $inner
    ) -WorkingDirectory $RootDir | Out-Null
    Write-Host "[start] $Title" -ForegroundColor Cyan
}

# Ensure a DB-backed service is listening; try Start-Service first, else run binary in a window.
function Ensure-Service {
    param([int]$Port, [string]$ServiceName, [string]$Title, [string]$FallbackCmd)
    if (Test-Port $Port) {
        Write-Host "[OK] $Title on 127.0.0.1:$Port" -ForegroundColor Green
        return
    }
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne "Running") {
        Write-Host "[WARN] starting service '$ServiceName' ..." -ForegroundColor Yellow
        Start-Service -Name $ServiceName -ErrorAction SilentlyContinue | Out-Null
    }
    if (Wait-Port $Port) {
        Write-Host "[OK] $Title on 127.0.0.1:$Port (service)" -ForegroundColor Green
        return
    }
    Open-Node -Title $Title -WorkDir $RootDir -Command $FallbackCmd
    if (Wait-Port $Port 30) {
        Write-Host "[OK] $Title on 127.0.0.1:$Port (process)" -ForegroundColor Green
    } else {
        Write-Host "[WARN] $Title not confirmed on 127.0.0.1:$Port yet" -ForegroundColor Yellow
    }
}

Write-Host "======== LX platform one-click start ========" -ForegroundColor Green
Write-Host "root: $RootDir"

# ---------- 1. databases ----------
# Redis: local service 'Redis' (fallback: bare redis-server)
if (Test-Port 6379) {
    Write-Host "[OK] Redis 127.0.0.1:6379" -ForegroundColor Green
} else {
    Ensure-Service -Port 6379 -ServiceName "Redis" -Title "Redis" `
        -FallbackCmd "& (Get-Command redis-server -ErrorAction SilentlyContinue).Source"
}

# MySQL: service name varies (MySQL80 / MySQL)
if (Test-Port 3306) {
    Write-Host "[OK] MySQL 127.0.0.1:3306" -ForegroundColor Green
} else {
    $mysqlNames = @("MySQL80", "MySQL")
    $svcUP = $null
    foreach ($n in $mysqlNames) {
        $s = Get-Service -Name $n -ErrorAction SilentlyContinue
        if ($s) { $svcUP = $s; break }
    }
    if ($svcUP) {
        Write-Host "[WARN] starting MySQL service..." -ForegroundColor Yellow
        Start-Service -Name $svcUP.Name -ErrorAction SilentlyContinue | Out-Null
    } else {
        Write-Host "[WARN] MySQL not listening on 3306 and no service found - start MySQL manually" -ForegroundColor Yellow
    }
    if (Wait-Port 3306) { Write-Host "[OK] MySQL 127.0.0.1:3306" -ForegroundColor Green }
}

# Neo4j: local service 'neo4j' (fallback: neo4j console)
if (Test-Port 7687) {
    Write-Host "[OK] Neo4j bolt://127.0.0.1:7687" -ForegroundColor Green
} else {
    Ensure-Service -Port 7687 -ServiceName "neo4j" -Title "Neo4j" -FallbackCmd "neo4j console"
}

# MinIO: not a service here -> always launch process if not listening
if (Test-Port 9000) {
    Write-Host "[OK] MinIO 127.0.0.1:9000" -ForegroundColor Green
} else {
    if (-not (Test-Path $MinioExe)) {
        Write-Host "[FATAL] MinIO exe not found: $MinioExe" -ForegroundColor Red
        exit 1
    }
    Open-Node -Title "MinIO(:9000/9001)" -WorkDir $RootDir -Command "& '$MinioExe' server '$MinioDataDir' --console-address ':9001'"
    if (Wait-Port 9000 40) { Write-Host "[OK] MinIO 127.0.0.1:9000" -ForegroundColor Green }
    else { Write-Host "[WARN] MinIO not confirmed on 9000 yet" -ForegroundColor Yellow }
}

# ---------- 2. backend ----------
Open-Node -Title "Backend(uvicorn:8000)" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m uvicorn app.main:app --reload --port 8000"

Open-Node -Title "Celery Worker" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph,training"

Open-Node -Title "Celery Beat" -WorkDir "$RootDir\backend" `
    -Command "& '$PySciMKG' -m celery -A app.core.celery_app beat -l info"

# ---------- 3. GraphRAGTest (needs LM Studio 1234 + Neo4j) ----------
Open-Node -Title "GraphRAGTest(8001)" -WorkDir "$RootDir\GraphRAGTest" -Command "& '$PyGraph' app.py"

# ---------- 4. frontend ----------
Open-Node -Title "Frontend(pnpm:3000)" -WorkDir "$RootDir\frontend" -Command "pnpm dev"

# ---------- 5. health-check summary ----------
Write-Host ""
Write-Host "======== waiting for services (health check) ========" -ForegroundColor Green
Start-Sleep -Seconds 5
$ports = @{ 9000 = "MinIO"; 8000 = "Backend"; 8001 = "GraphRAGTest"; 3000 = "Frontend" }
foreach ($k in $ports.Keys) {
    $ok = Wait-Port $k 40
    if ($ok) { Write-Host "[PASS] $($ports[$k])  http://localhost:$k" -ForegroundColor Green }
    else     { Write-Host "[FAIL] $($ports[$k])  http://localhost:$k not responding yet" -ForegroundColor Red }
}
Write-Host ""
Write-Host "======== services launched, verify ========" -ForegroundColor Green
Write-Host "  backend      http://localhost:8000/health"
Write-Host "  API docs     http://localhost:8000/docs"
Write-Host "  GraphRAG     http://localhost:8001/docs"
Write-Host "  frontend     http://localhost:3000"
Write-Host "  login        admin / admin123"
Write-Host "  MinIO ui     http://localhost:9001"
Write-Host "==========================================="