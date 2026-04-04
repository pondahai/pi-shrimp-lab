#!/bin/bash
# 新版小派自動部署腳本
# 執行環境：Raspberry Pi OS (Debian 12+)

echo "🚀 開始初始化新版小派環境..."

# 1. 更新系統並安裝核心依賴
sudo apt update && sudo apt install -y \
    python3-pip python3-venv git ffmpeg portaudio19-dev libportaudio2 \
    libatlas-base-dev i2c-tools python3-pil

# 2. 建立虛擬環境
python3 -m venv ~/xiaopai4_env
source ~/xiaopai4_env/bin/activate

# 3. 安裝 Python 核心與 AI 模型庫
pip install --upgrade pip
pip install faster-whisper sherpa-onnx numpy scipy sounddevice soundfile opencc cn2an adafruit-circuitpython-ssd1306 Pillow gpiozero

# 4. 準備模型目錄
mkdir -p ~/xiaopai4/model_files

echo "✅ 環境基礎建置完成。"
echo "⚠️ 請確認已將 model_files/ 資料夾搬移至 ~/xiaopai4/model_files/"
echo "✅ 準備就緒！"
