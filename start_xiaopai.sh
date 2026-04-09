#!/bin/bash
echo "清理舊的大腦引擎..."
pkill -f llama-server

echo "啟動大腦引擎 (llama-server) 在背景..."
nohup $HOME/llama.cpp/build/bin/llama-server -m $HOME/llama.cpp/models/gemma-4-E2B-it-UD-IQ2_M.gguf -c 2048 --port 8080 > $HOME/llama_server.log 2>&1 &

echo "等待大腦引擎載入模型 (約 5~10 秒)..."
sleep 10

echo "啟動小派聊天介面..."
$HOME/xiaopai_env/bin/python $HOME/xiaopai_chat.py

echo "關閉大腦引擎..."
pkill -f llama-server
