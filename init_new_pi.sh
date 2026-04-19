#!/bin/bash
# 🍓 小派 (Xiaopai) AI Agent 全自動初始化部署腳本
# 支援環境：Raspberry Pi 5 (Raspberry Pi OS 64-bit / Debian 12 Bookworm)
# 編纂日期：2026-04-19

set -e # 遇到錯誤即停止執行

echo "=================================================="
echo "🚀 開始初始化小派 (Xiaopai) 的全新環境..."
echo "=================================================="

# 1. 更新系統並安裝核心系統依賴
echo "📦 [1/6] 安裝系統工具與影音依賴..."
sudo apt update && sudo apt install -y \
    python3-pip python3-venv git ffmpeg portaudio19-dev libportaudio2 \
    libatlas-base-dev i2c-tools fonts-wqy-microhei python3-lgpio \
    cmake build-essential libcurl4-openssl-dev pkg-config \
    libjpeg-dev zlib1g-dev libcamera-apps

# 2. 建立專屬虛擬環境
echo "🐍 [2/6] 建立 Python 虛擬環境 (xiaopai_env)..."
if [ ! -d "$HOME/xiaopai_env" ]; then
    # 使用 --system-site-packages 以便存取系統級的 lgpio 驅動
    python3 -m venv --system-site-packages "$HOME/xiaopai_env"
fi
source "$HOME/xiaopai_env/bin/activate"

# 3. 安裝 Python 庫
echo "📚 [3/6] 安裝小派核心 Python 依賴..."
pip install --upgrade pip
# 安裝 rpi-lgpio 確保在 RPi 5 上 gpiozero 能正常工作
pip install numpy==1.24.3 faster-whisper sherpa-onnx \
    sounddevice soundfile luma.oled gpiozero Pillow rpi-lgpio

# 4. 下載與編譯本地大腦 (Llama.cpp)
echo "🧠 [4/6] 下載並編譯 Llama.cpp (本地推理引擎)..."
cd "$HOME"
if [ ! -d "$HOME/llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp.git
fi
cd llama.cpp
mkdir -p build && cd build
# 啟用 CURL 支援以供後續擴充
cmake .. -DGGML_CURL=ON
echo "⏳ 正在編譯 Llama.cpp，這可能需要幾分鐘時間..."
cmake --build . --config Release -j$(nproc)

# 5. 權限設定與目錄準備
echo "⚙️  [5/6] 設定硬體存取權限與目錄結構..."
sudo usermod -aG i2c,gpio,video $USER
mkdir -p "$HOME/xiaopai4/model_files"
mkdir -p "$HOME/llama.cpp/models"

# 6. 同步啟動腳本與主程式
echo "📑 [6/6] 同步小派核心程式碼至家目錄並設定自動啟動..."
if [ -d "$HOME/pi-shrimp-lab" ]; then
    cp "$HOME/pi-shrimp-lab/xiaopai_chat.py" "$HOME/"
    cp "$HOME/pi-shrimp-lab/xiaopai_menu.py" "$HOME/"
    cp "$HOME/pi-shrimp-lab/start_xiaopai.sh" "$HOME/"
    chmod +x "$HOME/start_xiaopai.sh"
    
    # 安裝 Systemd 服務
    echo "⚙️  正在安裝小派自動啟動服務..."
    sudo cp "$HOME/pi-shrimp-lab/xiaopai.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable xiaopai.service
    echo "✅ 自動啟動服務已安裝並啟用。"
fi

echo "=================================================="
echo "✅ 小派環境初始化建置成功！"
echo ""
echo "💡 服務管理指令："
echo "   啟動：sudo systemctl start xiaopai"
echo "   停止：sudo systemctl stop xiaopai"
echo "   狀態：sudo systemctl status xiaopai"
echo "   日誌：journalctl -u xiaopai -f"
echo ""
echo "💡 提醒："
echo "   請重新啟動樹莓派，或執行 'sudo systemctl start xiaopai' 來立即開始監聽三連擊！"
echo "=================================================="
