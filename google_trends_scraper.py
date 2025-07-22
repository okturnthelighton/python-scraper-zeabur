# 導入所有必要的函式庫
import os
import requests
import json
import urllib.parse
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException

# --- LINE 相關資訊 ---
# 從您在 Zeabur 設定的環境變數中讀取
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
# --- 結束 LINE 資訊部分 ---

def shorten_url(long_url):
    """使用 TinyURL API 縮短網址"""
    if not long_url or long_url.strip() == "" or long_url == "沒有找到相關連結":
        return "沒有找到相關連結"
    # 使用 safe='' 來確保整個 URL 被編碼
    api_url = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url, safe='')}"
    try:
        # 增加請求超時設定
        response = requests.get(api_url, timeout=10)
        # 檢查狀態碼，確保請求成功
        return response.text if response.status_code == 200 else long_url
    except requests.exceptions.RequestException as e:
        print(f"  > 縮短網址失敗: {e}")
        return long_url

def get_news_title_from_url(driver, url):
    """
    訪問新聞連結並提取標題。
    """
    if not url or url == "沒有找到相關連結" or url.startswith("https://www.google.com/search?q="):
        return "標題解析失敗或為備用連結"
    try:
        print(f"  > 正在訪問新聞連結以獲取標題: {url}")
        driver.get(url)
        # 等待 title 標籤出現，增加穩定性
        title_element = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "title")))
        page_title = title_element.get_attribute("textContent").strip()
        if page_title:
            print(f"  > 成功從 <title> 獲取標題: {page_title}")
            return page_title
        return "標題未找到"
    except TimeoutException:
        print(f"  > 訪問新聞連結超時: {url}")
        return "標題解析超時"
    except Exception as e:
        print(f"  > 訪問新聞連結或解析標題時發生錯誤：{e}")
        return "標題解析失敗"

def get_google_trends_data(driver):
    """
    爬取 Google Trends 的焦點新聞與所有熱門關鍵字。
    """
    detailed_trends = [] # 儲存 (keyword, link, title)
    all_keywords = [] # 儲存所有 keyword

    initial_url = "https://trends.google.com.tw/trending?geo=TW"
    print("正在載入 Google Trends 首頁...")
    driver.get(initial_url)
    
    try:
        print("等待熱門關鍵字列表渲染...")
        # 等待列表容器出現
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "feed-list-wrapper")))
        print("熱門關鍵字列表元素已載入。")
    except TimeoutException:
        print("⚠️ 等待首頁關鍵字列表超時。程式無法繼續。")
        return [], []

    # --- 首先，獲取所有關鍵字 (使用 BeautifulSoup) ---
    try:
        soup = BeautifulSoup(driver.page_source, "html5lib")
        # Google Trends 的 class 名稱可能會變，使用更通用的選擇器
        trend_elements = soup.find_all("div", class_="mZ3RIc")
        if trend_elements:
            print("\n--- 正在抓取所有熱門關鍵字 ---")
            for element in trend_elements:
                keyword = element.text.strip()
                if keyword:
                    all_keywords.append(keyword)
            print(f"成功抓取到 {len(all_keywords)} 個關鍵字。")
        else:
            print("ℹ️ 未能抓取到所有關鍵字的列表。")
    except Exception as e:
        print(f"❌ 抓取所有關鍵字列表時發生錯誤: {e}")

    # --- 接著，逐一處理焦點新聞 ---
    print("\n--- 正在逐一抓取焦點新聞詳情 ---")
    try:
        rows_xpath = '//tr[contains(@class, "UlR2Yc") and @data-row-id]'
        rows = driver.find_elements(By.XPATH, rows_xpath)
        num_rows = len(rows)
        print(f"找到 {num_rows} 個焦點新聞。")
    except NoSuchElementException:
        print("ℹ️ 在頁面上找不到任何焦點新聞列。")
        return [], all_keywords # 即使沒有焦點新聞，也要回傳已抓到的所有關鍵字

    for i in range(num_rows):
        keyword = f"未知(索引{i})" # 預設值
        try:
            # 每次循環都重新查找元素，避免 StaleElementReferenceException
            current_rows = driver.find_elements(By.XPATH, rows_xpath)
            if i >= len(current_rows):
                print(f"警告：元素數量在處理過程中減少，提前結束。")
                break
            
            row = current_rows[i]
            keyword_element = row.find_element(By.CLASS_NAME, "mZ3RIc")
            keyword = keyword_element.text.strip()
            print(f"\n- 正在處理第 {i+1}/{num_rows} 則焦點新聞: {keyword}")

            # 點擊進入詳細頁面
            driver.execute_script("arguments[0].click();", keyword_element)
            
            news_link = "沒有找到相關連結"
            news_title = "標題未找到"
            
            try:
                # 等待詳細頁面的新聞連結出現
                news_link_xpath = '//div[@class="jDtQ5"]//a[@class="xZCHj"]'
                news_link_element = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, news_link_xpath)))
                news_link = news_link_element.get_attribute('href')
                print(f"  ✨ 找到連結: {news_link}")
                news_title = get_news_title_from_url(driver, news_link)
            except TimeoutException:
                print("  ℹ️ 在詳細頁面沒有找到主要新聞連結，將使用備用搜尋連結。")
                news_link = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}"
                news_title = "搜尋結果 (備用連結)"

            detailed_trends.append((keyword, news_link, news_title))
            
            # [優化] 完成後，必須返回 Google Trends 首頁並等待其可互動
            print("  > 處理完成，返回 Google Trends 首頁。")
            driver.get(initial_url)
            # 使用更可靠的 WebDriverWait 替代 time.sleep
            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, rows_xpath))
            )

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
            print(f"❌ 處理焦點新聞 '{keyword}' 時發生瀏覽器互動錯誤：{e}")
            print("  > 嘗試重新載入 Google Trends 首頁以繼續...")
            try:
                driver.get(initial_url)
                WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc")))
            except Exception as retry_e:
                print(f"  > 重新載入失敗，放棄此輪迴圈: {retry_e}")
            continue # 繼續處理下一個關鍵字

    return detailed_trends, all_keywords

def send_to_line(detailed_trends, all_keywords):
    """將兩份報告合併成一條訊息發送到 LINE"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("❌ 缺少 LINE_ACCESS_TOKEN 或 LINE_USER_ID 環境變數，無法發送。")
        return
    
    if not detailed_trends and not all_keywords:
        print("ℹ️ 沒有任何數據可發送。")
        return

    # --- 組合訊息 ---
    message_parts = []
    
    # 第一部分：詳細新聞
    if detailed_trends:
        message_parts.append("📢 今日焦點新聞\n" + "-"*20)
        for i, (keyword, link, title) in enumerate(detailed_trends, 1):
            short_url = shorten_url(link)
            message_parts.append(f"{i}. {keyword}\n  📝 {title}\n  🔗 {short_url}")
    
    # 第二部分：所有熱門關鍵字
    if all_keywords:
        message_parts.append("\n📊 其他熱門關鍵字\n" + "-"*20)
        # 每行顯示 3 個關鍵字，讓訊息更緊湊
        keyword_lines = []
        line = []
        for keyword in all_keywords:
            line.append(keyword)
            if len(line) == 3:
                keyword_lines.append(" | ".join(line))
                line = []
        if line: # 處理剩下不滿 3 個的關鍵字
            keyword_lines.append(" | ".join(line))
        message_parts.append("\n".join(keyword_lines))

    full_message = "\n\n".join(message_parts)

    # --- 發送訊息 ---
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    # LINE 的訊息長度限制為 5000 字元，做個保險截斷
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": full_message[:4999]}]
    }
    try:
        print("正在發送訊息至 LINE...")
        response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data, timeout=15)
        response.raise_for_status() # 如果請求失敗 (如 4xx 或 5xx)，會拋出異常
        print("✅ 訊息發送成功！")
    except requests.exceptions.HTTPError as e:
        print(f"⚠️ 訊息發送失敗，HTTP 錯誤：{e.response.status_code} {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ 訊息發送失敗，請求錯誤：{e}")

if __name__ == "__main__":
    driver = None  # [關鍵修改] 先將 driver 初始化為 None
    try:
        print("----- 開始執行 Google Trends 爬蟲 -----")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") # 在 Docker/Linux 環境中非常重要
        options.add_argument("--window-size=1920,1080")
        
        print("正在初始化 Chrome WebDriver...")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60) # 設定頁面加載超時
        print("WebDriver 初始化成功。")

        detailed_trends_data, all_keywords_data = get_google_trends_data(driver)

        if detailed_trends_data or all_keywords_data:
            print("\n----- 準備發送訊息至 LINE -----")
            send_to_line(detailed_trends_data, all_keywords_data)
        else:
            print("⚠️ 今日沒有抓取到任何熱門數據。")

    except WebDriverException as e:
        # 特別處理 WebDriver 啟動失敗或運行時的嚴重錯誤
        print(f"❌ WebDriver 初始化失敗或運行時發生嚴重錯誤：{e}")
        print("請檢查 Docker 環境或 Chrome Driver 是否配置正確。")
    except Exception as e:
        # 處理所有其他預期外的錯誤
        print(f"❌ 程式執行過程中發生致命錯誤：{e}")
    finally:
        # [關鍵修改] 無論成功或失敗，只要 driver 被成功初始化過，就執行 quit
        if driver:
            print("\n準備關閉瀏覽器...")
            driver.quit()
            print("瀏覽器已關閉。")
        print("----- 程式執行完畢 -----")
