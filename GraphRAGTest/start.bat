@echo off
chcp 65001 >nul
echo ========================================
echo   GraphRAG 本地服务启动
echo ========================================
echo.

echo [1/3] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo.
echo [2/3] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/3] 启动 FastAPI 服务...
echo.
echo  启动完成后访问:
echo    Swagger UI:   http://localhost:8001/docs
echo    ReDoc:       http://localhost:8001/redoc
echo    LM Studio:   http://localhost:1234
echo.
echo  前置条件:
echo    - LM Studio 已启动并加载 qwen/qwen3-4b-2507
echo    - Neo4j 数据库已启动
echo.

python app.py

pause
