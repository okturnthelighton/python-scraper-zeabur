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
# [關鍵修改] 額外導入 Service 模組，用於指定驅動路徑
from selenium.webdriver.chrome.service import Service

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
    except requests.exceptions.RequestException as e:
        print(f"  > 縮短網址失敗: {e}")
        return long_url

def get_news_title_from_url(driver, url):
    """訪問新聞連結並提取標題。"""
    if not url or url == "沒有找到相關連結" or url.startswith("https://www.google.com/search?q="):
        return "標題解析失敗或為備用連結"
    try:
        print(f"  > 正在訪問新聞連結以獲取標題: {url}")
        driver.get(url)
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
    """爬取 Google Trends 的焦點新聞與所有熱門關鍵字。"""
    detailed_trends = []
    all_keywords = []
    initial_url = "https://trends.google.com.tw/trending?geo=TW"
    print("正在載入 Google Trends 首頁...")
    driver.get(initial_url)
    try:
        print("等待熱門關鍵字列表渲染...")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "feed-list-wrapper")))
        print("熱門關鍵字列表元素已載入。")
    except TimeoutException:
        print("⚠️ 等待首頁關鍵字列表超時。程式無法繼續。")
        return [], []
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
    print("\n--- 正在逐一抓取焦點新聞詳情 ---")
    try:
        rows_xpath = '//tr[contains(@class, "UlR2Yc") and @data-row-id]'
        rows = driver.find_elements(By.XPATH, rows_xpath)
        num_rows = len(rows)
        print(f"找到 {num_rows} 個焦點新聞。")
    except NoSuchElementException:
        print("ℹ️ 在頁面上找不到任何焦點新聞列。")
        return [], all_keywords
    for i in range(num_rows):
        keyword = f"未知(索引{i})"
        try:
            current_rows = driver.find_elements(By.XPATH, rows_xpath)
            if i >= len(current_rows):
                print(f"警告：元素數量在處理過程中減少，提前結束。")
                break
            row = current_rows[i]
            keyword_element = row.find_element(By.CLASS_NAME, "mZ3RIc")
            keyword = keyword_element.text.strip()
            print(f"\n- 正在處理第 {i+1}/{num_rows} 則焦點新聞: {keyword}")
            driver.execute_script("arguments[0].click();", keyword_element)
            news_link = "沒有找到相關連結"
            news_title = "標題未找到"
            try:
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
            print("  > 處理完成，返回 Google Trends 首頁。")
            driver.get(initial_url)
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, rows_xpath)))
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
            print(f"❌ 處理焦點新聞 '{keyword}' 時發生瀏覽器互動錯誤：{e}")
            print("  > 嘗試重新載入 Google Trends 首頁以繼續...")
            try:
                driver.get(initial_url)
                WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc")))
            except Exception as retry_e:
                print(f"  > 重新載入失敗，放棄此輪迴圈: {retry_e}")
            continue
    return detailed_trends, all_keywords

def send_to_line(detailed_trends, all_keywords):
    """將兩份報告合併成一條訊息發送到 LINE"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("❌ 缺少 LINE_ACCESS_TOKEN 或 LINE_USER_ID 環境變數，無法發送。")
        return
    if not detailed_trends and not all_keywords:
        print("ℹ️ 沒有任何數據可發送。")
        return
    message_parts = []
    if detailed_trends:
        message_parts.append("📢 今日焦點新聞\n" + "-"*20)
        for i, (keyword, link, title) in enumerate(detailed_trends, 1):
            short_url = shorten_url(link)
            message_parts.append(f"{i}. {keyword}\n  📝 {title}\n  🔗 {short_url}")
    if all_keywords:
        message_parts.append("\n📊 其他熱門關鍵字\n" + "-"*20)
        keyword_lines = []
        line = []
        for keyword in all_keywords:
            line.append(keyword)
            if len(line) == 3:
                keyword_lines.append(" | ".join(line))
                line = []
        if line:
            keyword_lines.append(" | ".join(line))
        message_parts.append("\n".join(keyword_lines))
    full_message = "\n\n".join(message_parts)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}
    data = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": full_message[:4999]}]}
    try:
        print("正在發送訊息至 LINE...")
        response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data, timeout=15)
        response.raise_for_status()
        print("✅ 訊息發送成功！")
    except requests.exceptions.HTTPError as e:
        print(f"⚠️ 訊息發送失敗，HTTP 錯誤：{e.response.status_code} {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ 訊息發送失敗，請求錯誤：{e}")

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
        
        # [關鍵修改] 創建一個 Service 物件，並明確指向 Dockerfile 中安裝的 chromium-driver 的路徑
        driver_service = Service(executable_path="/usr/bin/chromium-driver")
        
        print("正在初始化 Chrome WebDriver...")
        # [關鍵修改] 在初始化 webdriver.Chrome 時，傳入 service 物件
        driver = webdriver.Chrome(service=driver_service, options=options)
        
        driver.set_page_load_timeout(60)
        print("WebDriver 初始化成功。")

        detailed_trends_data, all_keywords_data = get_google_trends_data(driver)

        if detailed_trends_data or all_keywords_data:
            print("\n----- 準備發送訊息至 LINE -----")
            send_to_line(detailed_trends_data, all_keywords_data)
        else:
            print("⚠️ 今日沒有抓取到任何熱門數據。")

    except WebDriverException as e:
        # 更新錯誤訊息以反映新的設定
        print(f"❌ WebDriver 初始化失敗或運行時發生嚴重錯誤：{e}")
        print("請檢查 Dockerfile 中的 'chromium-driver' 是否已安裝，或 Python 中 Service 的路徑是否正確。")
    except Exception as e:
        print(f"❌ 程式執行過程中發生致命錯誤：{e}")
    finally:
        if driver:
            print("\n準備關閉瀏覽器...")
            driver.quit()
            print("瀏覽器已關閉。")
        print("----- 程式執行完畢 -----")
