# 🍓 樹莓派專案技術筆記：小派 (Xiaopai) AI 助手

## 1. 專案概述 (Project Overview)
*   **專案名稱：** 小派 (Xiaopai)
*   **運行硬體：** 樹莓派 5 (Raspberry Pi 5)
*   **主機位址：** `raspberry.local` (使用者: `pi`)
*   **核心目標：** 在樹莓派上運行一個輕量化、具備文字對話、OLED 顯示與語音回饋功能的本地 AI 語音/文字助手。

## 2. 系統架構與核心模組 (System Architecture)
*   **大腦引擎 (LLM Engine)：** 
    *   **軟體：** `llama.cpp` (`llama-server`)
    *   **模型：** Gemma 輕量化模型 (`gemma-4-E2B-it-UD-IQ2_M.gguf`，2-bit 量化)
    *   **服務端點：** 本地端 `http://127.0.0.1:8080/v1/chat/completions`
    *   **設定參數：** Context Size 2048, 系統提示詞設定為繁體中文、友善、簡潔的在地化人格。
*   **主控程式 (Chat Interface)：** 
    *   **程式檔：** `xiaopai_chat.py` (執行於虛擬環境 `~/xiaopai_env/bin/python`)
    *   **功能：** 負責接收輸入、向本地 API 發送請求、並協調 OLED 顯示與語音輸出。
*   **硬體周邊控制：**
    *   **OLED 螢幕：** 發送請求時顯示「(思考中...)」動畫，並動態逐字渲染 AI 的回應。
    *   **語音輸出 (Audio)：** 接收音效檔案並透過 `sounddevice` 播放，強制指定系統預設音效卡 (`sd.default.device = None`) 以解決資源佔用與衝突問題。

## 3. PC 端遠端控制與互動 (Remote Interaction)
為方便在 PC 端直接操作與監控，開發了專屬的 Python 遠端控制腳本：
*   **`run_xiaopai_interactive.py`**
    *   使用 `paramiko` 建立 SSH 連線。
    *   開啟 PTY 互動式通道 (Interactive Session) 並執行 `start_xiaopai.sh`。
    *   透過多執行緒 (`threading`) 實時監聽遠端標準輸出，實現「打字機效果」的對話體驗。
    *   直接於本地終端機輸入文字，即可透過 SSH 傳送至樹莓派的小派程式。

## 4. 關鍵維護與除錯指令 (Maintenance & Debugging)
*   **檢查運行中的進程：** `ps aux | grep -iE 'llama-server|xiaopai_chat' | grep -v grep`
*   **檢查大腦引擎日誌：** `tail -n 20 ~/llama_server.log`
*   **檢查系統記憶體狀態：** `free -m`
*   **重啟/強制關閉對話介面：** `pkill -f 'python.*xiaopai_chat.py'`
*   **本地除錯腳本：** 
    *   `debug_xiaopai.py`：一鍵遠端執行上述檢查指令。
    *   `patch_xiaopai_final.py`：用於熱更新樹莓派上的程式碼（如：修正音效卡衝突、加入思考動畫）。

---
*筆記產生時間：2026年4月9日*

## 5. 源碼分析與潛在問題 (Source Code Analysis)
*   **啟動流程：** `start_xiaopai.sh` 負責清理舊行程、於背景啟動 `llama-server` 提供 API，並執行 Python 主程式 `xiaopai_chat.py`。
*   **多模態輸入：** 結合了實體按鍵 (GPIO 22)、鍵盤輸入，並透過 `queue.Queue` 進行管理。短按清除記憶，長按錄音。語音轉文字使用 `faster_whisper`，並使用 `sherpa_onnx` 搭配自訂 Breeze 模型合成語音。
*   **視覺整合：** 輸入「看」、「拍照」等關鍵字會觸發相機拍攝，透過 `rpicam-jpeg` 擷取影像轉換為 Base64 格式，提交至 Vision 模型。
*   **已知問題 (待修復)：**
    1.  `xiaopai_chat.py` 中解析 API Server-Sent Events (SSE) 的迴圈內，使用了變數 `first_token`，但未在迴圈前初始化，可能會觸發 `NameError`。
    2.  視覺功能需依賴多模態投影檔 (mmproj)，但目前的 `start_xiaopai.sh` 啟動參數中未見 `--mmproj` 的設定，若觸發相機功能可能會收到 400 Bad Request。
