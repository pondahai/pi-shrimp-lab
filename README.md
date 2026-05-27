# 🍓 小派 (Xiaopai) AI Agent

小派是一個運行在樹莓派 5 上的智能代理系統，結合了多模態視覺、語音辨識與合成、以及 ReAct 自主行動邏輯。

## 🚀 快速開始

### 啟動系統
1. **停止背景衝突服務** (如果在 PC 上執行遠端互動腳本 `run_xiaopai_interactive.py`)：
   ```bash
   sudo systemctl stop xiaopai.service
   ```
2. **在樹莓派上直接啟動**：
   ```bash
   bash start_xiaopai.sh
   ```

### 操作指南 (GPIO 22 按鈕)
*   **啟動選單**：連續按三下（無論系統處於何種狀態）。
*   **選單操作**：
    *   **按一下**：切換下一個選項。
    *   **按兩下**：確認並啟動該模式。
*   **小派運行時**：
    *   **長按**：說話（語音模式）。
    *   **短按**：清除當前對話記憶。
    *   **連按三下**：跳回選單。

## 🛠️ 選單模式說明
1.  **API 雲端 (純文字)**：使用 Gemini API，停用語音。
2.  **本地大腦 (純文字)**：使用 llama-server (Gemma-4-E2B)，停用語音。
3.  **API 雲端 (語音)**：使用 Gemini API + Whisper + Sherpa-ONNX.
4.  **本地大腦 (語音)**：本地大腦 + 語音功能完整開啟。
5.  **關閉選單**：回到守護進程等待狀態。

## 🧠 最新升級與技術細節
### 1. Gemma 4 原生工具呼叫集成 (Native Tool Calling)
*   **優化**：移成了先前不穩定的手寫提示 JSON 和關鍵字攔截，全面升級為符合 **Gemma 4 與 OpenAI 規範的原生 `tools` 參數**。
*   **流程**：對話程式主動在 Payload 中宣告 Tool Schema，由 `llama-server` 透過 Gemma 4 的原生控制標記來解析和觸發。工具結果以 `role: "tool"` 搭配 `tool_call_id` 傳回大腦，確保極高的穩定性與智能體自主能力。

### 2. 本地大腦啟動延遲優化 (Startup Delay Tuning)
*   **調整**：為避免樹莓派 5 在加載 2.2GB Gemma 模型與 940MB `mmproj` 視覺投影模組時發生的 `503 Loading model` 錯誤，已將啟動等待時間從 `5s` 延長為 **`25s`**，保證大腦百分之百就緒。

### 3. 多模態相片快取 (Multimodal Frame Injection)
*   **機制**：當觸發拍照工具 `capture_and_analyze_vision` 時，程式會調用 `rpicam-jpeg` 生成影格，並將其 Base64 格式優雅地注入下一則對話中，提供完美的多模態感知體驗。

詳見 [Xiaopai_Tech_Note.md](./Xiaopai_Tech_Note.md)。
