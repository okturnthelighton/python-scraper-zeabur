# 步驟 1: 選擇基礎映像檔
# 我們選用官方的 Python 3.10-slim 版本，它是一個輕量級的 Linux 環境，已預先安裝好 Python。
FROM python:3.10-slim

# 步驟 2: 安裝系統依賴
# 在這個 Linux 環境中，我們需要安裝 Chromium 瀏覽器和對應的驅動程式。
# `apt-get` 是 Debian/Ubuntu Linux 上的套件管理工具。
# `--no-install-recommends` 可以避免安裝非必要的套件，讓環境更小。
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 步驟 3: 設定工作目錄
# 在容器（虛擬環境）內建立一個名為 /app 的資料夾，並將其設定為後續指令的執行目錄。
WORKDIR /app

# 步驟 4: 複製並安裝 Python 函式庫
# 先將 requirements.txt 複製到 /app 資料夾中。
COPY requirements.txt .
# 接著使用 pip 工具，根據 requirements.txt 的內容安裝所有 Python 函式庫。
RUN pip install --no-cache-dir -r requirements.txt

# 步驟 5: 複製您的應用程式程式碼
# 將您寫的 Python 主程式複製到 /app 資料夾中。
COPY google_trends_scraper.py .

# 步驟 6: 設定容器啟動時的預設指令
# 當 Zeabur 啟動這個環境時，會自動執行的指令。
# 這裡我們讓它執行您的 Python 爬蟲腳本。
CMD ["python3", "google_trends_scraper.py"]
