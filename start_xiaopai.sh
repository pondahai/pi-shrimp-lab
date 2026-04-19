#!/bin/bash

# --- 環境變數設定 ---
export GPIOZERO_PIN_FACTORY=lgpio
PYTHON_EXEC="/home/pi/xiaopai_env/bin/python"
HOME_DIR="/home/pi"

# 載入 API Key
if [ -f "$HOME_DIR/pi-shrimp-lab/.env" ]; then
    export $(cat "$HOME_DIR/pi-shrimp-lab/.env" | xargs)
fi

function launch_xiaopai() {
    local choice=$1
    [ -z "$choice" ] && return

    echo "正在啟動模式 $choice..."
    case $choice in
        1) export USE_CLOUD_LLM=1; export XIAOPAI_TEXT_ONLY=1 ;;
        2) export USE_CLOUD_LLM=0; export XIAOPAI_TEXT_ONLY=1 ;;
        3) export USE_CLOUD_LLM=1; export XIAOPAI_TEXT_ONLY=0 ;;
        4) export USE_CLOUD_LLM=0; export XIAOPAI_TEXT_ONLY=0 ;;
        5) echo "退出選單。"; return ;;
    esac

    if [ "$USE_CLOUD_LLM" == "0" ]; then
        pkill -f llama-server
        nohup $HOME_DIR/llama.cpp/build/bin/llama-server -m $HOME_DIR/llama.cpp/models/gemma-4-E2B-it-UD-IQ2_M.gguf --mmproj $HOME_DIR/llama.cpp/models/mmproj-F16.gguf -c 2048 --port 8080 > $HOME_DIR/llama_server.log 2>&1 &
        sleep 5
    fi

    $PYTHON_EXEC $HOME_DIR/xiaopai_chat.py
    local exit_code=$?
    
    pkill -f llama-server
    return $exit_code
}

echo "--- 小派守護程序啟動 ---"
echo "提示：無論何時，長按按鈕 4 秒可呼叫選單"

NEED_MENU=0

while true; do
    # 如果不需要立即顯示選單，則進入長按偵測模式
    if [ $NEED_MENU -eq 0 ]; then
        echo "[等待長按 4 秒...]"
        $PYTHON_EXEC -c "
import time, sys, os
from gpiozero import Button
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'
btn = Button(22, pull_up=True)
btn.hold_time = 4.0
def on_held():
    os._exit(0) # 成功偵測長按，正常退出
btn.when_held = on_held
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    os._exit(1)
"
        # 檢查偵測器退出代碼
        if [ $? -ne 0 ]; then
            sleep 1
            continue
        fi
    fi

    # 執行選單並獲取選擇內容
    echo "[啟動選單...]"
    CHOICE=$($PYTHON_EXEC $HOME_DIR/xiaopai_menu.py)
    
    if [ ! -z "$CHOICE" ]; then
        launch_xiaopai $CHOICE
        # 檢查小派是否是因為長按 4 秒才退出的 (退出碼 88)
        if [ $? -eq 88 ]; then
            NEED_MENU=1 # 下一輪迴圈直接顯示選單
        else
            NEED_MENU=0 # 正常退出，回到長按偵測模式
        fi
    else
        NEED_MENU=0
    fi
    
    sleep 0.5
done
