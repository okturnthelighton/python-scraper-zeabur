# 導入所有必要的函式庫，並額外導入 os
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
# 從環境變數讀取，這是雲端部署的最佳實踐
# 您需要在 Zeabur 的服務設定中，將這兩個值設定為環境變數
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
        if response.status_code == 200:
            return response.text
        else:
            print(f"⚠️ 縮短網址失敗，使用原網址：{long_url} (HTTP {response.status_code})")
            return long_url
    except requests.exceptions.RequestException as e:
        print(f"⚠️ 縮短網址時發生網路錯誤：{e}")
        return long_url
    except Exception as e:
        print(f"⚠️ 縮短網址時發生未知錯誤：{e}")
        return long_url

def get_news_title_from_url(driver, url, initial_url):
    """
    使用 Selenium 訪問給定 URL 並嘗試提取新聞標題。
    """
    if not url or url == "沒有找到相關連結" or url.startswith("https://www.google.com/search?q="):
        return "標題解析失敗或為備用連結"

    try:
        print(f"  > 正在訪問新聞連結以獲取標題: {url}")
        driver.get(url)
        time.sleep(3)

        # 嘗試從 <title> 標籤獲取標題
        title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "title"))
        )
        page_title = title_element.get_attribute("textContent").strip()
        if page_title:
            print(f"  > 成功從 <title> 獲取標題: {page_title}")
            return page_title
        
        # 如果 <title> 為空，嘗試其他常見元素
        soup = BeautifulSoup(driver.page_source, "html5lib")
        
        h1_title = soup.find("h1")
        if h1_title and h1_title.get_text(strip=True):
            print(f"  > 成功從 <h1> 獲取標題: {h1_title.get_text(strip=True)}")
            return h1_title.get_text(strip=True)

        h2_title = soup.find("h2")
        if h2_title and h2_title.get_text(strip=True):
            print(f"  > 成功從 <h2> 獲取標題: {h2_title.get_text(strip=True)}")
            return h2_title.get_text(strip=True)
            
        common_title_selectors = [
            {'name': 'div', 'class_': 'title'},
            {'name': 'span', 'class_': 'title'},
            {'name': 'div', 'id': 'news_title'},
            {'name': 'div', 'class_': 'article-title'},
            {'name': 'h1', 'class_': 'article-title'},
        ]
        
        for selector in common_title_selectors:
            if 'class_' in selector:
                found_title = soup.find(selector['name'], class_=selector['class_'])
            elif 'id' in selector:
                found_title = soup.find(selector['name'], id=selector['id'])
            
            if found_title and found_title.get_text(strip=True):
                print(f"  > 成功從 {selector['name']}.{selector.get('class_', selector.get('id'))} 獲取標題: {found_title.get_text(strip=True)}")
                return found_title.get_text(strip=True)

        print("  > 未能從新聞連結頁面提取到合適的標題。")
        return "標題未找到"

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"  > 訪問新聞連結或解析標題時發生 Selenium 錯誤：{e}")
        return "標題解析失敗"
    except Exception as e:
        print(f"  > 訪問新聞連結或解析標題時發生未知錯誤：{e}")
        return "標題解析失敗"
    # 注意：返回 Google Trends 的邏輯已移至主循環中，以確保每次都能正確返回

def get_google_trends_with_selenium():
    """使用 Selenium 爬取 Google Trends 熱門關鍵字、新聞連結及新聞標題"""
    chrome = None
    hot_trends_data = []
    initial_url = "https://trends.google.com.tw/trending?geo=TW"

    try:
        options = Options()
        # 在 Docker 環境中，必須使用 headless 模式
        options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox") # 在 Docker 中執行 Chrome 的必要參數
        options.add_argument("--disable-dev-shm-usage") # 克服有限的資源問題
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--log-level=3")

        # 【關鍵修改】移除 Service 物件，Selenium 4 會自動管理驅動程式
        chrome = webdriver.Chrome(options=options)
        chrome.set_page_load_timeout(60)

        print("正在載入 Google Trends 首頁...")
        chrome.get(initial_url)
        print("首頁載入完成，正在等待熱門關鍵字列表渲染...")

        try:
            WebDriverWait(chrome, 30).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc"))
            )
            print("熱門關鍵字列表元素已載入。")
        except TimeoutException:
            print("⚠️ 等待首頁關鍵字列表超時。")
            return []

        rows = chrome.find_elements(By.XPATH, '//tr[contains(@class, "UlR2Yc") and @data-row-id]')
        
        trend_elements_on_homepage = []
        for row in rows:
            try:
                row_id = int(row.get_attribute("data-row-id"))
                keyword_div = row.find_element(By.CLASS_NAME, "mZ3RIc")
                keyword = keyword_div.text.strip()
                if keyword:
                    trend_elements_on_homepage.append({
                        "row_id": row_id,
                        "keyword": keyword,
                        "element_to_click_xpath": f'//tr[@data-row-id="{row_id}"]//div[@class="mZ3RIc"]'
                    })
            except Exception as e:
                print(f"⚠️ 首頁解析單一趨勢項目時發生錯誤: {e}")
                continue

        print(f"首頁共發現 {len(trend_elements_on_homepage)} 個熱門關鍵字。")

        for trend_info in trend_elements_on_homepage:
            keyword = trend_info["keyword"]
            row_id = trend_info["row_id"]
            element_xpath = trend_info["element_to_click_xpath"]
            
            print(f"\n--- 正在處理關鍵字: [{row_id}] {keyword} ---")
            
            try:
                clickable_element = WebDriverWait(chrome, 15).until(
                    EC.element_to_be_clickable((By.XPATH, element_xpath))
                )
                chrome.execute_script("arguments[0].click();", clickable_element)
                print(f"成功點擊關鍵字 '{keyword}'，正在載入詳細頁面...")
                
                WebDriverWait(chrome, 25).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@class="jDtQ5"]//a[@class="xZCHj"]'))
                )
                print(f"詳細頁面新聞連結元素已載入。")
                time.sleep(1)

                detail_soup = BeautifulSoup(chrome.page_source, "html5lib")
                news_content_div = detail_soup.find("div", class_="jDtQ5")
                news_link = "沒有找到相關連結"
                news_title = "標題未找到"

                if news_content_div and news_content_div.find("a", class_="xZCHj"):
                    news_link = news_content_div.find("a", class_="xZCHj")['href']
                    print(f"✨ 找到連結: {news_link}")
                    # 獲取標題
                    news_title = get_news_title_from_url(chrome, news_link, initial_url)
                else:
                    print("ℹ️ 在詳細頁面沒有找到主要新聞連結，將使用備用連結。")
                    news_link = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}"
                    news_title = "搜尋結果 (備用連結)"

                hot_trends_data.append((keyword, news_link, news_title))
                
                # 完成一個關鍵字處理後，必須返回 Google Trends 首頁
                print("  > 處理完成，返回 Google Trends 首頁以繼續。")
                chrome.get(initial_url)
                WebDriverWait(chrome, 15).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc"))
                )
                time.sleep(1.5)

            except Exception as e:
                print(f"❌ 處理關鍵字 '{keyword}' 時發生錯誤：{e}")
                print("嘗試重新載入 Google Trends 首頁以繼續...")
                try:
                    chrome.get(initial_url)
                    WebDriverWait(chrome, 20).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, "mZ3RIc"))
                    )
                    print("成功重新載入 Google Trends 首頁。")
                    time.sleep(2)
                except Exception as re_e:
                    print(f"⚠️ 無法重新載入 Google Trends 首頁，程式可能無法繼續：{re_e}")
                    break # 如果無法恢復，則中斷循環
                continue

        if hot_trends_data:
            print(f"\n總共成功抓取到 {len(hot_trends_data)} 個趨勢。")
        else:
            print("沒有找到任何趨勢。")

    except Exception as e:
        print(f"❌ 爬蟲過程中發生致命錯誤：{e}")
    finally:
        if chrome is not None:
            chrome.quit()
            print("\n瀏覽器已關閉。")
    
    return hot_trends_data

def send_to_line(hot_trends_data):
    """將熱門關鍵字、連結及標題發送到 LINE"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("❌ 缺少 LINE_ACCESS_TOKEN 或 LINE_USER_ID 環境變數，無法發送訊息。")
        return
    
    if not hot_trends_data:
        print("ℹ️ 沒有關鍵字數據可發送，跳過 LINE 訊息。")
        return

    message_header = "📢 今日 Google Trends 熱門關鍵字及新聞:\n"
    current_message_part = message_header
    
    for i, (keyword, original_link, news_title) in enumerate(hot_trends_data, 1):
        short_url = shorten_url(original_link)
        new_line = f"{i}. {keyword}\n  📝 {news_title}\n  🔗 {short_url}\n"
        
        # 檢查加上新內容後是否會超過 LINE 的單次訊息長度限制 (約 5000 字元)
        if len(current_message_part.encode('utf-8')) + len(new_line.encode('utf-8')) > 4800:
            # 發送當前累積的訊息
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
            }
            data = {
                "to": LINE_USER_ID,
                "messages": [{"type": "text", "text": current_message_part.strip()}]
            }
            try:
                response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data)
                response.raise_for_status()
                print(f"✅ 訊息分段發送成功！")
                time.sleep(1)
                current_message_part = "📢 (續) Google Trends 熱門關鍵字及新聞:\n"
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 訊息分段發送失敗：{e}")
                current_message_part = "📢 (續) Google Trends 熱門關鍵字及新聞:\n"
        
        current_message_part += new_line

    # 發送最後剩餘的訊息
    if current_message_part.strip() != message_header.strip() and \
       current_message_part.strip() != "📢 (續) Google Trends 熱門關鍵字及新聞:":
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
        }
        data = {
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": current_message_part.strip()}]
        }
        try:
            response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data)
            response.raise_for_status()
            print("✅ 最後一段訊息發送成功！")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 最後一段訊息發送失敗：{e}")

if __name__ == "__main__":
    print("----- 開始執行 Google Trends 爬蟲與 LINE 推播 -----")
    hot_trends_data = get_google_trends_with_selenium()

    if hot_trends_data:
        print("\n----- 準備發送訊息至 LINE -----")
        send_to_line(hot_trends_data)
    else:
        print("⚠️ 今日沒有熱門搜尋數據，不發送 LINE 訊息。")
    print("----- 程式執行完畢 -----")
