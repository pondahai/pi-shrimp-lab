# 🍓 樹莓派專案技術筆記：小派 (Xiaopai) AI 代理

## 1. 系統架構：Agentic Loop 
*   **核心模式**：ReAct (Reasoning and Acting)。小派不再是簡單的 Q&A 機器人，而是一個能根據 JSON Schema 自主決定下一步動作的代理。
*   **大腦引擎**：
    *   **雲端 (優先)**：Google Gemini API (Gemma-4-31B-it)。透過 OpenAI 兼容端點 (`v1beta/openai`) 連接。
    *   **本地 (降級備援)**：`llama-server` 執行 `gemma-4-E2B-it-UD-IQ2_M.gguf`。
*   **視覺處理**：掛載 `mmproj-F16.gguf` 視覺投影檔，支援多模態輸入。

## 2. 關鍵技術實作細節
*   **JSON 強制輸出**：API 請求中設定 `response_format: {"type": "json_object"}`，確保模型輸出符合思考 (thought)、工具 (tool_name)、訊息 (message) 的結構。
*   **認證繞過 (Google API Auth Bug)**：
    針對 Google API 對 API Key 的特殊處理，手動注入 `Authorization: Bearer ` (後帶空白) 配合 `x-goog-api-key` Header，避免 `Multiple authentication credentials` 衝突。
*   **內容清洗機制**：
    1.  正規表達式過濾 `<thought>` 標籤。
    2.  清除 Markdown 的 ```json 代碼塊。
    3.  型別檢查與字串化轉換。

## 3. 工具函式庫 (Tools Registry)
| 工具名稱 | 功能說明 | 安全機制 |
| :--- | :--- | :--- |
| `get_current_time` | 獲取當前日期與精確秒數 | 無 |
| `get_system_status` | 讀取 /sys/class/thermal 溫度與 free -m | 無 |
| `capture_and_analyze_vision` | 調用 rpicam-jpeg 拍照並送入 Vision 模型 | 自動封裝多模態訊息 |
| `execute_shell_command` | 執行 Linux 指令 | **指令白名單**: ls, ping, df, uptime, free |

## 4. 運維與故障排除
*   **網路連線測試**：`ping -c 1 -W 2 generativelanguage.googleapis.com`
*   **本地引擎日誌**：`tail -f ~/llama_server.log`
*   **代理狀態監控**：觀察 Python 控制台輸出的 `[系統] 正在呼叫工具` 字樣。

---
*技術筆記更新於：2026-04-18，由 Gemini CLI 編纂*
