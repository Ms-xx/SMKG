<#
.SYNOPSIS
    启动 MLflow 本地 tracking server（步骤 14.3：MLflow 本地 tracking server 接入）。

.DESCRIPTION
    在「本地部署」唯一官方支持模式下，拉起一台独立的 MLflow tracking server：
      - 后端存储（backend store）：位于独立存储目录下的 SQLite 库 <MLFLOW_HOME>/backend/mlflow.db
      - 工件存储（artifact store）：位于独立存储目录下的 <MLFLOW_HOME>/artifacts
      - 运行日志：<MLFLOW_HOME>/logs/mlflow_server.log
    存储目录与项目其他资源（moulds / outputs / backend/storage 等）完全隔离。

    路径全部**参数化、无硬编码**：
      - 存储根目录由 -TrackingHome 或环境变量 MLFLOW_HOME 决定，缺省 = <仓库根>/mlflow
        （仓库根由本脚本位置自动推导，因此克隆到任意磁盘/目录均可直接运行）
      - Python 解释器由 -PythonExe / 环境变量 MLFLOW_PYTHON 决定，缺省依次回退到
        当前虚拟环境（VIRTUAL_ENV）与 PATH 上的 python

.PARAMETER TrackingHome
    MLflow 独立存储根目录。缺省取环境变量 MLFLOW_HOME，仍为空则用 <仓库根>/mlflow。

.PARAMETER BindHost
    监听地址，缺省 127.0.0.1（仅本机，符合本地部署口径）。

.PARAMETER Port
    监听端口，缺省 5000。

.PARAMETER PythonExe
    运行 mlflow 的 Python 解释器路径。缺省按 MLFLOW_PYTHON → VIRTUAL_ENV → python 回退。

.EXAMPLE
    pwsh -File deploy/mlflow/start_mlflow_server.ps1
    # 默认：<仓库根>/mlflow，127.0.0.1:5000

.EXAMPLE
    $env:MLFLOW_HOME = "D:/mlflow-data"; pwsh -File deploy/mlflow/start_mlflow_server.ps1 -Port 5001
#>
[CmdletBinding()]
param(
    [string]$TrackingHome = $env:MLFLOW_HOME,
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 5000,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# 解释器解析（无硬编码）：显式 -PythonExe > 环境变量 MLFLOW_PYTHON > 当前虚拟环境 > PATH 上的 python
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if ($env:MLFLOW_PYTHON) {
        $PythonExe = $env:MLFLOW_PYTHON
    } elseif ($env:VIRTUAL_ENV) {
        $PythonExe = Join-Path $env:VIRTUAL_ENV "Scripts/python.exe"
    } else {
        $PythonExe = "python"
    }
}

# ── 1. 推导仓库根与存储目录（无硬编码）────────────────────────────────
# 本脚本位于 <仓库根>/deploy/mlflow/，向上两级即仓库根
$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ScriptDir) -and $MyInvocation.MyCommand.Path) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($ScriptDir)) {
    $ScriptDir = (Get-Location).Path
}
$RepoRoot = (Resolve-Path (Join-Path -Path $ScriptDir -ChildPath "..\..")).Path
if ([string]::IsNullOrWhiteSpace($TrackingHome)) {
    $TrackingHome = Join-Path -Path $RepoRoot -ChildPath "mlflow"
}
$TrackingHome = [System.IO.Path]::GetFullPath($TrackingHome)

$BackendDir = Join-Path -Path $TrackingHome -ChildPath "backend"
$ArtifactDir = Join-Path -Path $TrackingHome -ChildPath "artifacts"
$LogDir = Join-Path -Path $TrackingHome -ChildPath "logs"
$BackendDb = Join-Path -Path $BackendDir -ChildPath "mlflow.db"
$LogFile = Join-Path -Path $LogDir -ChildPath "mlflow_server.log"

foreach ($d in @($TrackingHome, $BackendDir, $ArtifactDir, $LogDir)) {
    if (-not (Test-Path -Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

# ── 2. 组装 URI（Windows 盘符需转正斜杠 + file:/// 三斜杠）────────────
function ConvertTo-UriPath([string]$p) { return ($p -replace '\\', '/') }
$BackendStoreUri = "sqlite:///" + (ConvertTo-UriPath $BackendDb)
$ArtifactRootUri = "file:///" + (ConvertTo-UriPath $ArtifactDir)

# ── 3. 解析解释器并校验 mlflow 可用 ────────────────────────────────────
try {
    $MlflowVersion = & $PythonExe -c "import mlflow; print(mlflow.__version__)" 2>&1
} catch {
    Write-Error "无法用解释器 '$PythonExe' 导入 mlflow，请先安装（pip install mlflow）或用 -PythonExe 指定。$_"
    exit 1
}

# ── 4. 打印生效配置 ────────────────────────────────────────────────────
Write-Host "== MLflow 本地 tracking server ==" -ForegroundColor Cyan
Write-Host "  解释器        : $PythonExe (mlflow $MlflowVersion)"
Write-Host "  存储根目录    : $TrackingHome"
Write-Host "  后端存储 URI  : $BackendStoreUri"
Write-Host "  工件存储 URI  : $ArtifactRootUri"
Write-Host "  运行日志      : $LogFile"
Write-Host "  监听地址      : http://$BindHost`:$Port"
Write-Host ""

# ── 5. 启动服务 ────────────────────────────────────────────────────────
# 用 Start-Process 拉起独立进程：① stdout/stderr 直接落盘，避免 PowerShell 把 MLflow 的
# stderr 提示当作错误终止脚本；② 进程独立于本脚本存活，关闭终端不影响服务运行。
$ErrLogFile = Join-Path -Path $LogDir -ChildPath "mlflow_server.err.log"
$serverArgs = @(
    "-m", "mlflow", "server",
    "--backend-store-uri", $BackendStoreUri,
    "--default-artifact-root", $ArtifactRootUri,
    "--host", $BindHost,
    "--port", "$Port"
)

$proc = Start-Process -FilePath $PythonExe -ArgumentList $serverArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput $LogFile -RedirectStandardError $ErrLogFile
Write-Host "  进程 PID      : $($proc.Id)"
Write-Host "  服务日志      : $LogFile"
Write-Host "  错误日志      : $ErrLogFile"
Write-Host ""

# ── 6. 就绪探测（最多等待 20s）────────────────────────────────────────
$HealthUrl = "http://$BindHost`:$Port/health"
$Ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $Ready = $true; break }
    } catch { }
}
if ($Ready) {
    Write-Host "启动就绪：$HealthUrl -> HTTP 200（MLflow tracking server 已就绪）" -ForegroundColor Green
} else {
    Write-Host "启动未就绪（20s 内未返回 200），请查看 $StderrLog" -ForegroundColor Yellow
}
