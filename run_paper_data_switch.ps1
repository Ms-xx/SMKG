# ============================================================================
#  run_paper_data_switch.ps1 - 论文数据切换端到端一键执行（测试流程）
#  用法：
#    powershell -NoProfile -ExecutionPolicy Bypass -File .\run_paper_data_switch.ps1
#  可选参数：
#    -Mode clear-all（默认，全量清空）| delete-user（仅删指定用户，保留他人数据）
#  流程：启动服务 -> inventory 只读预演 -> 清理旧数据 -> ingest 197 篇 -> 汇总
#  产物：outputs\paper_data_switch_<cmd>_<时间戳>.json（各步骤报告）
#        outputs\paper_data_switch_e2e_<时间戳>.log（全程控制台日志）
#  前提：LM Studio(qwen3-4b:1234) 建议开启（LLM 抽取；未开启回退规则模板）
# ============================================================================
param(
    [string]$Mode = "clear-all",
    [string]$UserUuid = "462111b8-37f5-11f1-98d0-b025aa39c5bf",
    [string]$PdfDir = "download_data\Paper"
)

$ErrorActionPreference = "Continue"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RootDir
$Py = "D:\workapp\Anaconda\anaconda3\envs\SciMKG\python.exe"

if (-not (Test-Path $PdfDir)) {
    Write-Host "[FATAL] PDF 源目录不存在: $PdfDir" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path outputs | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "outputs\paper_data_switch_e2e_$ts.log"
Start-Transcript -Path $log | Out-Null
Write-Host "======== 论文数据切换端到端执行 ======== $(Get-Date)" -ForegroundColor Green
Write-Host "模式: $Mode | 用户: $UserUuid | PDF 目录: $PdfDir"
Write-Host "日志: $log"

# ---- 步骤 0：前置检查 ----
if (-not (Test-Path $Py)) {
    Write-Host "[FATAL] SciMKG python 不存在: $Py" -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}
$pdfCount = (Get-ChildItem "$PdfDir\*.pdf" -ErrorAction SilentlyContinue).Count
Write-Host "[步骤0] SciMKG python OK；PDF 数量: $pdfCount"
Write-Host "[提醒] GraphRAG/LLM 抽取建议先开启 LM Studio(qwen3-4b:1234)；未开启时自动回退规则模板，不阻断流程。"

# ---- 步骤 1：一键启动全套服务（MySQL/Redis/Neo4j/MinIO/后端/Celery/前端）----
Write-Host "`n[步骤1] 调用官方 start_all.ps1 启动服务..." -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File .\start_all.ps1 -Mode Production

# ---- 步骤 2：等待后端 8000 就绪 ----
Write-Host "`n[步骤2] 等待后端就绪（最长 180s）..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(180)
$backendOk = $false
while ((Get-Date) -lt $deadline) {
    if (Test-NetConnection 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue |
        Where-Object { $_.TcpTestSucceeded }) { $backendOk = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $backendOk) {
    Write-Host "[FATAL] 后端 180s 内未就绪，请查看服务窗口日志后重试" -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "[OK] 后端 127.0.0.1:8000 已就绪"

# ---- 步骤 3：inventory 只读清单预演 ----
Write-Host "`n[步骤3] inventory 只读预演..." -ForegroundColor Cyan
& $Py backend\scripts\paper_data_switch.py inventory --user-uuid $UserUuid
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FATAL] inventory 失败，查看上方日志" -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}

# ---- 步骤 4：清理旧数据（脚本内置交互二次确认，输入 yes 才执行）----
Write-Host "`n[步骤4] 清理旧数据（模式: $Mode，将提示输入 yes 确认）..." -ForegroundColor Cyan
if ($Mode -eq "delete-user") {
    & $Py backend\scripts\paper_data_switch.py delete-user --user-uuid $UserUuid
} else {
    & $Py backend\scripts\paper_data_switch.py clear-all --enable-http-cache
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FATAL] 清理失败，查看上方日志" -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}

# ---- 步骤 5：197 篇新 PDF 批量入库（login->upload->parse->全文->建图闭环）----
Write-Host "`n[步骤5] 批量入库新 PDF（耗时较长，请耐心等待）..." -ForegroundColor Cyan
& $Py backend\scripts\paper_data_switch.py ingest --dir $PdfDir
$ingestCode = $LASTEXITCODE

# ---- 步骤 6：读取 ingest 报告并汇总 ----
Write-Host "`n[步骤6] 汇总 ingest 报告..." -ForegroundColor Cyan
$rep = Get-ChildItem "outputs\paper_data_switch_ingest_*.json" |
    Sort-Object LastWriteTime | Select-Object -Last 1
if ($rep) {
    Write-Host "ingest 报告: $($rep.FullName)"
    Get-Content $rep.FullName -Raw | Write-Host
} else {
    Write-Host "[WARN] 未找到 ingest 报告 JSON" -ForegroundColor Yellow
}

Stop-Transcript | Out-Null
Write-Host "`n======== 执行结束（ingest 退出码 $ingestCode）======== $(Get-Date)" -ForegroundColor Green
Write-Host "全程日志: $log"
exit $ingestCode