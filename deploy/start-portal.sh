#!/bin/bash
# LLM Portal 启动脚本

PORTAL_DIR="/mnt/ssd/soft/llm-portal"
BACKEND_PORT=8606
FRONTEND_PORT=6300
LOG_DIR="$PORTAL_DIR/logs"

# 创建日志目录
mkdir -p $LOG_DIR

# 先停止可能存在的旧进程
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "vite.*$FRONTEND_PORT" 2>/dev/null
sleep 2

# 激活 conda 环境
source /mnt/ssd/soft/miniconda3/etc/profile.d/conda.sh
conda activate llm-portal-env

# 启动后端
echo "Starting backend on port $BACKEND_PORT..."
cd $PORTAL_DIR/backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > $LOG_DIR/backend.log 2>&1 &
echo $! > $LOG_DIR/backend.pid
sleep 3

# 启动前端（指定端口）
echo "Starting frontend on port $FRONTEND_PORT..."
cd $PORTAL_DIR/frontend
nohup npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT > $LOG_DIR/frontend.log 2>&1 &
echo $! > $LOG_DIR/frontend.pid

sleep 2
echo "LLM Portal started!"
echo "Frontend: http://192.168.31.24:$FRONTEND_PORT"
echo "Backend:  http://192.168.31.24:$BACKEND_PORT"
echo "API Docs: http://192.168.31.24:$BACKEND_PORT/docs"
echo "Logs: $LOG_DIR"
