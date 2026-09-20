#!/bin/bash
# 前端启动脚本

echo "🚀 启动前端开发服务器..."

# 检查Node.js和pnpm
if ! command -v node &> /dev/null; then
    echo "❌ Node.js未安装，请先安装Node.js"
    exit 1
fi

if ! command -v pnpm &> /dev/null; then
    echo "❌ pnpm未安装，正在安装pnpm..."
    npm install -g pnpm
fi

# 检查依赖是否安装
if [ ! -d "node_modules" ]; then
    echo "📦 正在安装依赖..."
    pnpm install
fi

# 检查后端服务是否启动
echo "🔍 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ 后端服务正常运行"
else
    echo "⚠️  后端服务未启动，请先启动后端服务"
    echo "   启动命令: cd ../backend && uvicorn app.main:app --reload --port 8000"
fi

# 启动前端开发服务器
echo "🌟 启动Vite开发服务器..."
pnpm dev

echo "✅ 前端服务启动完成!"
echo "📍 前端地址: http://localhost:3000"
echo "📚 API文档: http://localhost:8000/docs"