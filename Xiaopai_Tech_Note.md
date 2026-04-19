# 🍓 樹莓派專案技術筆記：小派 (Xiaopai) AI 代理

## 1. 系統架構：Agentic Loop 
*   **核心模式**：ReAct (Reasoning and Acting)。小派不再是簡單的 Q&A 機器人，而是一個能根據 JSON Schema 自主決定下一步動作的代理。
*   **交互選單 (New)**：`xiaopai_menu.py` 透過 OLED 與實體按鍵提供啟動選項。支援單擊切換、雙擊確認、長按 4 秒全域切換。
*   **大腦引擎**：
    *   **雲端 (優先)**：Google Gemini API (Gemma-4-31B-it)。透過 OpenAI 兼容端點 (`v1beta/openai`) 連接。
    *   **本地 (降級備援)**：`llama-server` 執行 `gemma-4-E2B-it-UD-IQ2_M.gguf`。

## 2. 關鍵技術實作細節
*   **全時長按監聽**：
    1.  `start_xiaopai.sh` 使用 Python 子進程監聽 GPIO 22 長按。
    2.  `xiaopai_chat.py` 內建 `when_held` 邏輯，長按 4 秒以 Exit Code 88 退出，觸發 Shell 跳回選單。
*   **語音文本正規化 (TTS Normalization)**：
    針對 Sherpa-ONNX 無法發音數字與 Emoji 的限制，實作 `normalize_for_tts`：
    - 阿拉伯數字 (0-99) 自動轉換為中文字元。
    - 移除所有 Emoji 與不支援的特殊符號。
    - 英文詞彙轉換 (如 AI -> 欸哀, CPU -> 希披優)。
*   **JSON 強制輸出與防禦性解析**：
    強化 `choices` 與 `content` 欄位檢查，捕捉 `finish_reason: safety` 等異常狀態避免崩潰。

## 3. 工具函式庫 (Tools Registry)
| 工具名稱 | 功能說明 | 安全機制 |
| :--- | :--- | :--- |
| `get_current_time` | 獲取當前日期與精確秒數 | 無 |
| `get_system_status` | 讀取 /sys/class/thermal 溫度與 free -m | 無 |
| `capture_and_analyze_vision` | 調用 rpicam-jpeg 拍照並送入 Vision 模型 | 自動封裝多模態訊息 |
| `execute_shell_command` | 執行 Linux 指令 | **白名單**: ls, ping, df, uptime, free, **curl** (限定 wttr.in/api) |

## 4. 運維與故障排除
*   **選單切換**：長按 GPIO 22 按鈕 4 秒。
*   **本地引擎日誌**：`tail -f ~/llama_server.log`
*   **語音偵錯**：觀察控制台輸出的 `[語音同步]` 字樣確認正規化結果。

---
*技術筆記更新於：2026-04-19，由 Gemini CLI 編纂*
