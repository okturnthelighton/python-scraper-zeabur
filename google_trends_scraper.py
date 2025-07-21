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
    api_url = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url, safe='')}"
    try:
        response = requests.get(api_url, timeout=10)
        return response.text if response.status_code == 200 else long_url
    except requests.exceptions.RequestException:
        return long_url

def get_news_title_from_url(driver, url):
    """
    (來自第一個腳本) 訪問新聞連結並提取標題。
    """
    if not url or url == "沒有找到相關連結" or url.startswith("https://www.google.com/search?q="):
        return "標題解析失敗或為備用連結"
    try:
        print(f"  > 正在訪問新聞連結以獲取標題: {url}")
        driver.get(url)
        # 等待 title 標籤出現
        title_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "title")))
        page_title = title_element.get_attribute("textContent").strip()
        if page_title:
            print(f"  > 成功從 <title> 獲取標題: {page_title}")
            return page_title
        return "標題未找到"
    except Exception as e:
        print(f"  > 訪問新聞連結或解析標題時發生錯誤：{e}")
        return "標題解析失敗"

def get_google_trends_data(driver):
    """
    合併後的爬蟲主函式：
    1. 獲取包含新聞標題的詳細趨勢 (舊腳本功能)
    2. 獲取所有熱門關鍵字的列表 (新腳本功能)
    """
    detailed_trends = [] # 儲存 (keyword, link, title)
    all_keywords = [] # 儲存所有 keyword

    initial_url = "https://trends.google.com.tw/trending?geo=TW"
    print("正在載入 Google Trends 首頁...")
    driver.get(initial_url)
    
    try:
        print("等待熱門關鍵字列表渲染...")
        WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc")))
        print("熱門關鍵字列表元素已載入。")
    except TimeoutException:
        print("⚠️ 等待首頁關鍵字列表超時。")
        return [], []

    # --- 首先，執行新腳本的邏輯：獲取所有關鍵字 ---
    try:
        soup = BeautifulSoup(driver.page_source, "html5lib")
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

    # --- 接著，執行第一個腳本的邏輯：點擊每個趨勢獲取詳細新聞 ---
    print("\n--- 正在逐一抓取焦點新聞詳情 ---")
    rows = driver.find_elements(By.XPATH, '//tr[contains(@class, "UlR2Yc") and @data-row-id]')
    
    for i in range(len(rows)):
        try:
            # 每次循環都重新查找元素，避免 StaleElementReferenceException
            current_rows = driver.find_elements(By.XPATH, '//tr[contains(@class, "UlR2Yc") and @data-row-id]')
            if i >= len(current_rows):
                break # 如果元素數量變少，則跳出
            
            row = current_rows[i]
            keyword = row.find_element(By.CLASS_NAME, "mZ3RIc").text.strip()
            print(f"\n- 正在處理焦點新聞: {keyword}")

            # 點擊進入詳細頁面
            driver.execute_script("arguments[0].click();", row.find_element(By.CLASS_NAME, "mZ3RIc"))
            
            news_link = "沒有找到相關連結"
            news_title = "標題未找到"
            
            try:
                # 等待詳細頁面的新聞連結出現
                news_link_element = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, '//div[@class="jDtQ5"]//a[@class="xZCHj"]')))
                news_link = news_link_element.get_attribute('href')
                print(f"  ✨ 找到連結: {news_link}")
                news_title = get_news_title_from_url(driver, news_link)
            except TimeoutException:
                print("  ℹ️ 在詳細頁面沒有找到主要新聞連結，將使用備用連結。")
                news_link = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}"
                news_title = "搜尋結果 (備用連結)"

            detailed_trends.append((keyword, news_link, news_title))
            
            # 完成後，必須返回 Google Trends 首頁
            print("  > 處理完成，返回 Google Trends 首頁。")
            driver.get(initial_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc")))
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ 處理焦點新聞 '{keyword}' 時發生錯誤：{e}")
            print("  > 嘗試重新載入 Google Trends 首頁以繼續...")
            driver.get(initial_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc")))
            continue

    return detailed_trends, all_keywords

def send_to_line(detailed_trends, all_keywords):
    """將兩份報告合併成一條訊息發送到 LINE"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("❌ 缺少 LINE_ACCESS_TOKEN 或 LINE_USER_ID 環境變數。")
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
        keyword_lines = []
        for i, keyword in enumerate(all_keywords, 1):
            keyword_lines.append(f"{i}. {keyword}")
        message_parts.append("\n".join(keyword_lines))

    full_message = "\n".join(message_parts)

    # --- 發送訊息 ---
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    # LINE 的訊息長度限制為 5000 字元，我們的內容通常不會超過
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": full_message[:4999]}] # 做個保險
    }
    try:
        response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data)
        response.raise_for_status()
        print("✅ 訊息發送成功！")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ 訊息發送失敗：{e}")

if __name__ == "__main__":
    driver = None
    try:
        print("----- 開始執行 Google Trends 爬蟲 -----")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        detailed_trends_data, all_keywords_data = get_google_trends_data(driver)

        if detailed_trends_data or all_keywords_data:
            print("\n----- 準備發送訊息至 LINE -----")
            send_to_line(detailed_trends_data, all_keywords_data)
        else:
            print("⚠️ 今日沒有抓取到任何熱門數據。")

    except Exception as e:
        print(f"❌ 程式執行過程中發生致命錯誤：{e}")
    finally:
        if driver:
            driver.quit()
            print("\n瀏覽器已關閉。")
        print("----- 程式執行完畢 -----")
