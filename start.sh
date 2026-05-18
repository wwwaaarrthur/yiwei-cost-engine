#!/bin/bash
# 毅伟成本核算系统启动脚本
# 用法：在 Mac 终端执行 bash ~/.openclaw/workspace/yiwei-cost-engine/start.sh

cd ~/.openclaw/workspace/yiwei-cost-engine
source .venv/bin/activate
echo "🚀 正在启动毅伟成本核算系统..."
echo ""
echo "📍 访问方式："
echo "   Mac 本机浏览器:  http://localhost:8501"
echo "   同WiFi手机/平板: http://192.168.0.44:8501"
echo ""
echo "⏹  按 Ctrl+C 停止"
echo ""
python3 -m streamlit run app.py --server.headless true
