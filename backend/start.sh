# 后端启动脚本

echo "正在启动后端服务..."

# 1. 检查数据库连接
echo "检查数据库连接..."
python -c "from sqlalchemy import create_engine; from app.core.config import settings; engine = create_engine(settings.DATABASE_URL.replace('+aiomysql', '+pymysql')); engine.connect(); print('数据库连接成功')"

# 2. 初始化数据库(如果是首次启动)
echo "是否需要初始化数据库? (y/n)"
read -t 5 answer
if [ "$answer" = "y" ]; then
    echo "正在初始化数据库..."
    python scripts/init_db.py
fi

# 3. 启动FastAPI服务
echo "启动FastAPI服务..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 启动Celery Worker(在另一个终端)
# celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph

# 5. 启动Celery Beat(定时任务,可选)
# celery -A app.core.celery_app beat -l info

echo "后端服务启动完成!"
echo "API文档地址: http://localhost:8000/docs"
echo "ReDoc地址: http://localhost:8000/redoc"