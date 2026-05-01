#!/bin/bash
# LLM Portal 停止脚本

PORTAL_DIR="/mnt/ssd/soft/llm-portal"
LOG_DIR="$PORTAL_DIR/logs"

echo "Stopping LLM Portal..."

# 停止前端
if [ -f "$LOG_DIR/frontend.pid" ]; then
    PID=$(cat $LOG_DIR/frontend.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "Frontend stopped (PID: $PID)"
    fi
    rm -f $LOG_DIR/frontend.pid
fi

# 停止后端
if [ -f "$LOG_DIR/backend.pid" ]; then
    PID=$(cat $LOG_DIR/backend.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "Backend stopped (PID: $PID)"
    fi
    rm -f $LOG_DIR/backend.pid
fi

# 清理可能的孤儿进程
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "vite.*6300" 2>/dev/null

echo "LLM Portal stopped."
