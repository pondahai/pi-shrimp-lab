#!/bin/bash
# 處理命令行參數
XIAOPAI_TEXT_ONLY=0
for arg in "$@"; do
    if [ "$arg" == "--text" ]; then
        XIAOPAI_TEXT_ONLY=1
        echo ">>> 設定為純文字模式 (Text-Only Mode) <<<"
    fi
done

echo "清理舊的大腦引擎..."
pkill -f llama-server

echo "檢查網路連線..."
if [ -f "$HOME/pi-shrimp-lab/.env" ]; then
    export $(cat "$HOME/pi-shrimp-lab/.env" | xargs)
fi

if ping -c 1 -W 2 generativelanguage.googleapis.com > /dev/null 2>&1; then
    echo "網路暢通，將使用雲端 Google API 大腦 (gemma-4-31b-it)..."
    export USE_CLOUD_LLM=1
else
    echo "網路不通，啟動本地大腦引擎 (llama-server) 在背景..."
    export USE_CLOUD_LLM=0
    nohup $HOME/llama.cpp/build/bin/llama-server -m $HOME/llama.cpp/models/gemma-4-E2B-it-UD-IQ2_M.gguf --mmproj $HOME/llama.cpp/models/mmproj-F16.gguf -c 2048 --port 8080 > $HOME/llama_server.log 2>&1 &
    
    echo "等待本地大腦引擎載入模型 (約 5~10 秒)..."
    sleep 10
fi

echo "啟動小派聊天介面..."
export XIAOPAI_TEXT_ONLY=$XIAOPAI_TEXT_ONLY
$HOME/xiaopai_env/bin/python $HOME/xiaopai_chat.py

if [ "$USE_CLOUD_LLM" != "1" ]; then
    echo "關閉本地大腦引擎..."
    pkill -f llama-server
fi
