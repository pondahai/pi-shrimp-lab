# 🦞 pi-shrimp-lab (小派實驗室)

這是一個專門存放 Raspberry Pi 邊緣運算專案的資產庫。這裡記錄了小派 (Xiaopai) 的「核心大腦」與「部署藍圖」。

## 🚀 專案重大更新 (2026-04-18)
目前小派已升級為 **Agentic AI 代理架構**，具備自主思考與工具調用能力。

### 🌟 核心特性
- **Agentic Design (代理設計)**：基於 JSON 結構化輸出實作 Agent Loop，模型會先思考 (Thought) 再決定是否呼叫工具。
- **Hybrid LLM Engine (雙引擎切換)**：
    - **Cloud Mode**：網路通暢時，自動連接 Google Gemini API 使用強大的 `gemma-4-31b-it` 大模型。
    - **Local Mode**：網路斷線時，自動降級執行本地 `llama.cpp` (Gemma-4-E2B-it)。
- **多模態視覺系統**：成功掛載 `mmproj-F16.gguf`，支援即時拍照、畫面分析與多輪對話。
- **內建工具箱 (Tools)**：
    - `get_current_time`: 精準時間查詢。
    - `get_system_status`: CPU 溫度、記憶體狀態監控。
    - `capture_and_analyze_vision`: 視覺感官調用。
    - `execute_shell_command`: 安全指令執行 (白名單控制)。

## 📁 內容清單
- `xiaopai_chat.py`: **主程式**。整合 Agent 邏輯、多重 API 認證與語音互動。
- `start_xiaopai.sh`: **智能啟動腳本**。自動執行網路檢測、模型載入與環境設定。
- `init_new_pi.sh`: 自動化部署腳本。

## 🧠 硬體架構
- **主機**: Raspberry Pi 5 (8GB 建議)
- **顯示**: I2C SSD1306 OLED (128x64)
- **輸入**: GPIO 22 實體按鍵 (短按清記憶、長按錄音)
- **語音**: Google VoiceHAT (48000Hz 採樣率)

---
*由 Gemini CLI 自動更新於 2026-04-18*
