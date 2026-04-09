#!/bin/bash

MODEL="$HOME/llama.cpp/models/gemma-4-E2B-it-UD-IQ2_M.gguf"
CLI="$HOME/llama.cpp/build/bin/llama-cli"

echo "=================================================="
echo "    🧠 啟動「小派」的大腦 (Gemma 4-E2B 2-bit)...  "
echo "=================================================="
echo "小派：你好！我是小派，我已經準備好了。你可以隨時跟我說話！"
echo "(輸入 Ctrl+C 即可離開)"
echo "--------------------------------------------------"

$CLI -m "$MODEL" \
     -c 2048 \
     -n 512 \
     --temp 0.6 \
     -cnv \
     --chat-template gemma \
     --system-prompt "你是「小派」，一個運行在樹莓派 5 上的聰明 AI 助手。你的大腦是 Gemma 輕量化模型。你的回答要簡潔、友善，且使用繁體中文。請不要輸出過長的回應。" \
     --color
