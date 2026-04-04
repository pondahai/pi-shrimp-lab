# 🦞 pi-shrimp-lab (小派實驗室)

這是一個專門存放 Raspberry Pi 邊緣運算專案的資產庫。這裡記錄了你舊版小派的「靈魂」與「部署藍圖」，確保未來在任何新卡片或新硬體上，都能在 30 分鐘內復刻你的語音 AI 實驗室。

## 📁 內容清單
- `init_new_pi.sh`: **自動化部署腳本**。自動安裝系統依賴、建立虛擬環境、pip 核心套件。
- `xiaopai3_full_backup.tar.gz`: **遺產備份**。包含舊小派中經人工調校的 TTS 模型參數、發音辭典 (lexicon) 與自定義 Python 腳本。

## 🚀 復盤/重建流程 (SOP)
當你拿到一張新的 SD 卡時，請遵循以下步驟：

1. **安裝 OS 後執行初始化**：
   ```bash
   chmod +x init_new_pi.sh
   ./init_new_pi.sh
   ```
2. **復原核心靈魂**：
   ```bash
   tar -xzvf xiaopai3_full_backup.tar.gz -C ~/xiaopai4/
   ```
3. **啟動自動化服務**：
   (參考 `xiaopai.service` 設定)
   ```bash
   sudo cp xiaopai.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable xiaopai
   sudo systemctl start xiaopai
   ```

## 🧠 核心技術背景
- **推理引擎**: LiteRT-LM (新版), sherpa-onnx (舊版語音)
- **硬體架構**: Raspberry Pi 5 + SSD1306(I2C)
- **語音特徵參數**: 
    - `noise_scale`: 0.333
    - `noise_scale_w`: 0.2
    - `length_scale`: 1.1

---
*記錄於 2026-04-04，由 OpenClaw 小蝦編纂*
