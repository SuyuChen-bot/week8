import requests
from bs4 import BeautifulSoup
import urllib3

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# 判斷是在 Vercel 還是本地
if os.path.exists('serviceAccountKey.json'):
    # 本地環境：讀取檔案
    cred = credentials.Certificate('serviceAccountKey.json')
else:
    # 雲端環境：從環境變數讀取 JSON 字串
    firebase_config = os.getenv('FIREBASE_CONFIG')
    cred_dict = json.loads(firebase_config)
    cred = credentials.Certificate(cred_dict)

firebase_admin.initialize_app(cred)


from flask import Flask, render_template,request
from datetime import datetime

# 1. 初始化 Firebase (確保這段程式碼有執行到)
if not firebase_admin._apps:
    if os.path.exists('serviceAccountKey.json'):
        cred = credentials.Certificate('serviceAccountKey.json')
    else:
        firebase_config = os.getenv('FIREBASE_CONFIG')
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

# 2. 【關鍵修正】定義全域變數 db
# 必須放在這裡，所有路由函式 (@app.route) 才能讀到它
db = firestore.client()

from flask import jsonify

app = Flask(__name__)

@app.route("/")
def index():
    link = "<h1>歡迎進入陳素宥的網站首頁</h1>"
    link += "<a href=/mis>課程</a><hr>"
    link += "<a href=/today>今天日期</a><hr>"
    link += "<a href=/about>關於素宥</a><hr>"
    link += "<a href=/welcome?u=素宥&dep=靜宜資管>GET傳值</a><hr>"
    link += "<a href=/account>POST傳值(帳號密碼)</a><hr>"
    link += "<a href=/math>數學運算</a><hr>"
    link += "<a href=/read>讀取Firestore資料(根據lab遞減排序，取前4筆)</a><hr>"
    link += "<a href=/search>靜宜資管老師查詢</a><hr>"
    link += "<a href=/sp1>爬蟲</a><hr>"
    link += "<a href=/movie>查詢即將上映電影</a><hr>"
    link += "<a href=/movie2>爬取電影進資料庫</a><hr>"
    link += "<a href=/movie3>查詢電影資料庫</a><hr>"
    link += "<a href=/road>台中市十大肇事路口</a><hr>"
    link += "<a href=/weather>天氣查詢</a><hr>"
    link += "<a href=/rate>本周新片</a><hr>"
    return link

from datetime import datetime  # 確保檔案頂部有這行


@app.route("/webhook", methods=['POST'])
def webhook():
    # 接收 Dialogflow 的請求
    req = request.get_json(silent=True, force=True)
    
    # 取得 Dialogflow 傳來的分級參數 (例如：普遍級)
    # 請確保 Dialogflow 中的參數名稱也是 "rate"
    target_rate = req.get("queryResult").get("parameters").get("rate")

    # 1. 邏輯檢查：到 Firestore 進行篩選
    # 使用你剛才創立的集合名稱 "本週新片含分級"
    movies_ref = db.collection("本週新片含分級")
    docs = movies_ref.where("rate", "==", target_rate).get()
    
    movie_list = []
    for doc in docs:
        m = doc.to_dict()
        movie_list.append(m.get("title"))

    # 2. 姓名標示：在訊息開頭加上你的名字
    if movie_list:
        reply = f"陳素宥您好！為您查詢到本週上映的 {target_rate} 電影有：\n"
        reply += "、".join(movie_list)
    else:
        reply = f"陳素宥您好，目前資料庫中沒有找到符合 {target_rate} 的電影喔。"

    # 回傳給 Dialogflow 顯示
    return jsonify({"fulfillmentText": reply})
    
@app.route("/rate")
def rate():
    # 爬取開眼電影「本週新片」
    url = "https://www.atmovies.com.tw/movie/new/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        Data = requests.get(url, headers=headers, verify=False)
        Data.encoding = "utf-8"
        sp = BeautifulSoup(Data.text, "html.parser")
        
        # 取得更新日期
        lastUpdate_element = sp.find(class_="smaller09")
        lastUpdate = lastUpdate_element.text[5:] if lastUpdate_element else "未知"
        
        result = sp.select(".filmList")
        count = 0

        for x in result:
            title = x.find("a").text
            introduce = x.find("p").text
            movie_id = x.find("a").get("href").replace("/", "").replace("movie", "")
            hyperlink = "http://www.atmovies.com.tw/movie/" + movie_id
            picture = f"https://www.atmovies.com.tw/photo101/{movie_id}/pm_{movie_id}.jpg"

            # 分級判斷邏輯
            r_tag = x.find(class_="runtime").find("img")
            rate_label = "未分級"
            if r_tag:
                rr = r_tag.get("src").replace("/images/cer_", "").replace(".gif", "")
                mapping = {"G": "普遍級", "P": "保護級", "F2": "輔12級", "F5": "輔15級", "R": "限制級"}
                rate_label = mapping.get(rr, "限制級")

            # 解析片長與上映日期
            t_text = x.find(class_="runtime").text
            showLength = "0"
            showDate = "未知"
            if "片長" in t_text:
                showLength = t_text[t_text.find("片長")+3 : t_text.find("分")]
            if "上映日期" in t_text:
                # 擷取原始字串，例如 "5/8/2026"
                rawDate = t_text[t_text.find("上映日期")+5 : t_text.find("上映廳數")-8].strip()
                
                # --- 日期補零處理開始 ---
                try:
                    # 解析原始格式 (月/日/年)
                    date_obj = datetime.strptime(rawDate, "%m/%d/%Y")
                    # 轉換為目標格式 (年/月/日) 並自動補零，例如 "2026/05/08"
                    showDate = date_obj.strftime("%Y/%m/%d")
                except:
                    showDate = rawDate  # 若格式不符則保留原始狀態
                # --- 日期補零處理結束 ---

            doc = {
                "title": title,
                "introduce": introduce,
                "picture": picture,
                "hyperlink": hyperlink,
                "showDate": showDate,
                "showLength": int(showLength) if showLength.isdigit() else 0,
                "rate": rate_label,
                "lastUpdate": lastUpdate
            }

            # 儲存至 Firestore
            db.collection("本週新片含分級").document(movie_id).set(doc)
            count += 1

        return f"<h2>成功！</h2>已爬取 {count} 部新片，存檔至「本週新片含分級」集合。<br>網站更新日期：{lastUpdate}<br><br><a href='/'>回首頁</a>"
    
    except Exception as e:
        return f"<h2>爬取失敗</h2>錯誤訊息：{e}<br><a href='/'>回首頁</a>"

@app.route("/weather", methods=["GET", "POST"])
def weather():
    import requests
    import json
    import urllib3

    # 關閉 InsecureRequestWarning 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    city = request.values.get("city")
    
    # HTML 表單介面 (維持你 movie3 的寫法風格)
    form_html = """
    <h2>縣市天氣查詢</h2>
    <form action="/weather" method="POST">
        <input type="text" name="city" placeholder= "{val}">
        <button type="submit">查詢</button>
    </form>
    <hr>
    """.format(val=city if city else "")

    if not city:
        return form_html + "請輸入縣市名稱進行查詢。<br><br><a href='/'>回首頁</a>"

    # --- 以下是你提供的範本邏輯 ---
    city = city.replace("台","臺")
    token = "rdec-key-123-45678-011121314"
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=" + token + "&format=JSON&locationName=" + str(city)

    try:
        # 加入 verify=False 參數
        Data = requests.get(url, verify=False, timeout=10) 
        
        JsonData = json.loads(Data.text)
        
        # 判斷是否有抓到資料
        if JsonData["records"]["location"]:
            Weather = JsonData["records"]["location"][0]["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
            Rain = JsonData["records"]["location"][0]["weatherElement"][1]["time"][0]["parameter"]["parameterName"]
            
            result_msg = f"<h3>{city} 的天氣是：{Weather}，降雨機率：{Rain}%</h3>"
        else:
            result_msg = f"<h3>找不到「{city}」的天氣資料，請確認輸入是否正確。</h3>"
            
    except Exception as e:
        result_msg = f"<h3>查詢失敗：{str(e)}</h3>"
    
    # --- 範本邏輯結束 ---

    return form_html + result_msg + "<br><a href='/'>回首頁</a>"

@app.route("/road")
def get_road_data():
    import requests
    import urllib3
    
    # 關閉 SSL 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"
    
    # 使用 Session 保持連線會話
    session = requests.Session()
    
    # 更完整的瀏覽器標頭偽裝
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        # 使用 session 進行請求，並增加 timeout
        response = session.get(url, headers=headers, verify=False, timeout=20)
        
        if response.status_code == 200:
            json_data = response.json()
            result_list = ["<h2>台中市十大肇事路口</h2>"]
            
            for item in json_data:
                msg = f" {item['路口名稱']}：總共發生 <b>{item['總件數']}</b> 件事故"
                result_list.append(msg)
            
            return "<br>".join(result_list) + "<br><br><a href='/'>回首頁</a>"
        
        else:
            return f"伺服器回應錯誤碼：{response.status_code} <br><a href='/'>回首頁</a>"

    except Exception as e:
        # 如果還是 10054，說明對方的防火牆可能暫時封鎖了你的 IP
        return f"<h3>目前無法連線至政府資料庫</h3>錯誤代碼：10054<br>原因：伺服器拒絕了連線請求。<br>建議：請等待 1 分鐘後再重新整理，或檢查電腦是否開啟了 VPN。<br><br><a href='/'>回首頁</a>"
import re  # 記得在檔案最上方加入這行

import re

import re


@app.route("/movie3", methods=["GET", "POST"])
def movie3():
    db = firestore.client()
    keyword = request.values.get("keyword")
    
    # HTML 表單
    form_html = """
    <h2>即將上映查詢</h2>
    <form action="/movie3" method="POST">
        <input type="text" name="keyword" placeholder="請輸入電影片名關鍵字" value="{val}">
        <button type="submit">查詢</button>
    </form>
    <hr>
    """.format(val=keyword if keyword else "")

    if not keyword:
        return form_html + "請輸入關鍵字搜尋資料庫中的電影。<br><br><a href='/'>回首頁</a>"

    # 查詢資料庫
    docs = db.collection("UpcomingMovies").get()
    result_html = ""
    found = False

    for doc in docs:
        m = doc.to_dict()
        if keyword in m.get("name", ""):
            result_html += f"電影名稱：{m.get('name')}<br>"
            result_html += f"更新日期：{m.get('update')}<br>"
            result_html += f"連結：<a href='{m.get('url')}' target='_blank'>電影介紹</a><br><hr>"
            found = True

    if not found:
        result_html = f"找不到包含「{keyword}」的電影資料。"

    return form_html + result_html + "<br><a href='/'>回首頁</a>"

@app.route("/movie2")
def movie2():
    db = firestore.client()
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    blacklist = ["電影首頁", "本期二輪", "電影", "List All", "本周新片", "本期首輪", "近期上映", "新片快報", "票房排行榜", "資料館"]
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    count = 0
    debug_msg = "" # 用來紀錄過程，方便除錯

    try:
        # 1. 抓取網頁
        data = requests.get(url, headers=headers, timeout=10)
        data.encoding = "utf-8"
        sp = BeautifulSoup(data.text, "html.parser")
        links = sp.find_all("a")
        
        debug_msg += f"成功讀取網頁，發現 {len(links)} 個連結。<br>"

        # 2. 解析並存檔
        for link in links:
            href = link.get("href")
            title = link.text.strip()
            
            if href and "/movie/" in href and len(title) > 1:
                if title not in blacklist and not any(word in title for word in ["電影首頁", "List All"]):
                    # 移除日期文字
                    clean_title = re.sub(r'^(\d{4}/)?\d{1,2}/\d{1,2}\s*', '', title)
                    
                    if clean_title and clean_title not in blacklist:
                        full_url = "http://www.atmovies.com.tw" + href
                        
                        # 寫入 Firestore
                        doc_ref = db.collection("UpcomingMovies").document(clean_title)
                        doc_ref.set({
                            "name": clean_title,
                            "url": full_url,
                            "update": update_time
                        })
                        count += 1

        # 3. 確保回傳結果給瀏覽器
        if count > 0:
            return f"</h2>近期上映電影已爬蟲及存檔完畢，網站最近更新日期為：{update_time}<br><br><a href='/'>回首頁</a>"
        else:
            return f"<h2>更新完成，但沒有抓到新電影。</h2>過程紀錄：{debug_msg}<br><a href='/'>回首頁</a>"

    except Exception as e:
        # 如果發生錯誤（例如 Firebase 沒連上），會顯示在這裡
        return f"<h2>執行失敗</h2>錯誤訊息：{e}<br><br><a href='/'>回首頁</a>"


@app.route("/movie")
def movie():
    R = "<h2>開眼即將上映電影</h2>"
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 定義要刪除的無效名稱（黑名單）
    blacklist = ["電影首頁", "本期二輪", "電影", "List All", "本周新片", "本期首輪", "近期上映", "新片快報", "票房排行榜", "資料館"]
    
    try:
        data = requests.get(url, headers=headers, timeout=10)
        data.encoding = "utf-8"
        sp = BeautifulSoup(data.text, "html.parser")
        links = sp.find_all("a")
        
        movie_list = []
        for link in links:
            href = link.get("href")
            title = link.text.strip()
            
            # 1. 基本篩選：必須是電影連結且文字長度大於 1
            if href and "/movie/" in href and len(title) > 1:
                
                # 2. 黑名單篩選：剔除你提到的那些選單文字
                if title not in blacklist and not any(word in title for word in ["電影首頁", "List All"]):
                    
                    # 3. 強力去日期：不管開頭是 2026/05/07 還是 5/7
                    clean_title = re.sub(r'^(\d{4}/)?\d{1,2}/\d{1,2}\s*', '', title)
                    
                    # 4. 再次確認 clean_title 不是空的且不在黑名單內
                    if clean_title and clean_title not in blacklist:
                        full_url = "http://www.atmovies.com.tw" + href
                        
                        # 5. 避免重複抓取
                        if clean_title not in [m['name'] for m in movie_list]:
                            movie_list.append({"name": clean_title, "url": full_url})

        # 輸出結果
        for m in movie_list:
            R += f"電影名稱：{m['name']}<br>"
            R += f"連結：<a href='{m['url']}' target='_blank'>{m['url']}</a><br><hr>"
            
        if not movie_list:
            R += "目前沒抓到電影，請檢查網頁是否改版。"

    except Exception as e:
        R += f"發生錯誤：{e}"
    
    R += "<br><a href='/'>回首頁</a>"
    return R

@app.route("/sp1")
def sp1():
    R = "<h2>關於網頁內容爬取</h2>"
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 注意：在 Vercel 環境中 127.0.0.1 是抓不到內容的
    # 這裡建議改為抓取你部署後的正式網址，或是直接分析 templates 內容
    url = "https://www1.pu.edu.tw/~tcyang/course.html" 
    try:
        Data = requests.get(url, verify=False)
        Data.encoding = "utf-8"
        sp = BeautifulSoup(Data.text, "html.parser")
        result = sp.select("td a")

        for item in result:
            # 修正：item 是標籤物件，不能直接相加，要用 .text
            R += f"連結文字: {item.text}<br>"
            R += f"網址: {item.get('href')}<br><br>"
    except Exception as e:
        R += f"抓取失敗：{e}"
        
    R += "<br><a href='/'>回首頁</a>"
    return R




@app.route("/search")
def search():
    db = firestore.client()
    collection_ref = db.collection("靜宜資管2026a")
    
    # 1. 取得使用者輸入的關鍵字
    keyword = request.values.get("keyword")
    
    # 2. 建立 HTML 表單字串
    # 注意這裡：action 必須改成 "/search"，否則按下按鈕會跳到 404
    # placeholder 加上引號，並加入 value="{val}" 讓輸入的字留在框框裡
    form_html = """
    <h2>靜宜資管老師查詢</h2>
    <p>請輸入老師姓名關鍵字：</p>
    <form action="/search" method="GET" style="margin-bottom: 20px;">
        <input type="text" name="keyword" placeholder=>
        <button type="submit">搜尋</button>
    </form>
    <hr>
    """.format(val=keyword if keyword else "")

    # 3. 邏輯判斷：如果沒有 keyword，直接回傳表單
    if not keyword:
        return form_html + "請輸入關鍵字進行搜尋。<br><br><a href='/'>回首頁</a>"

    # 4. 如果有關鍵字，才讀取資料庫
    docs = collection_ref.order_by("lab").get()
    
    Temp = ""
    found_count = 0
    
    for doc in docs:
        user = doc.to_dict()
        user_name = user.get("name", "")
        
        # 核心篩選邏輯
        if keyword in user_name:
            Temp += f"名字: {user_name}, Lab: {user.get('lab')}<br>"
            found_count += 1

    # 5. 組合搜尋結果
    if found_count > 0:
        result_msg = f"<h3>關鍵字「{keyword}」的搜尋結果：</h3>"
    else:
        result_msg = f"<h3>搜尋結果：</h3>找不到包含「{keyword}」的資料。"

    return form_html + result_msg + Temp + "<br><br><a href='/'>回首頁</a>"

@app.route("/read")
def read():
    db = firestore.client()

    Temp = ""
    collection_ref = db.collection("靜宜資管2026a")
    #docs = collection_ref.where(filter=FieldFilter("lab",">", "579")).get()
    docs = collection_ref.order_by("lab").limit(4).get()
    for doc in docs:
        Temp += str(doc.to_dict()) + "<br>"

    return Temp

@app.route("/mis")
def course():
    return "<h1>資訊管理導論</h1>"

@app.route("/today")
def today():
    now = datetime.now()
    year = str(now.year)    #取得年分
    month = str(now.month)  #取得月份
    day = str(now.day)      #取得日期
    now = year + "年" + month + "月" + day + "日"
    return render_template("today.html", datetime = now)

@app.route("/about")
def about():
	return render_template("MIS2A7.html")

@app.route("/welcome", methods=["GET"])
def welcome():
    x = request.values.get("u")
    y = request.values.get("dep")
    return render_template("welcome.html", name= x,dep = y)

@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        user = request.form["user"]
        pwd = request.form["pwd"]
        result = "您輸入的帳號是：" + user + "; 密碼為：" + pwd 
        return result
    else:
        return render_template("account.html")

@app.route('/math', methods=['GET', 'POST'])
def math():
    Result = None
    error_msg = None
    x, y, opt = None, None, None

    if request.method == 'POST':
        try:
            # 從表單取得資料
            x = int(request.form.get('x'))
            y = int(request.form.get('y'))
            opt = request.form.get('opt')

            # 你的核心邏輯：判斷除數與運算
            if opt == "/" and y == 0:
                error_msg = "錯誤：除數不能為 0"
            else:
                match opt:
                    case "+": Result = x + y
                    case "-": Result = x - y
                    case "*": Result = x * y
                    case "/": Result = x / y
                    case "%": Result = x % y
                    case _: error_msg = f"錯誤：不支援的符號 '{opt}'"
        except (ValueError, TypeError):
            error_msg = "請輸入有效的數字"

    return render_template('math.html', Result=Result, error_msg=error_msg, x=x, y=y, opt=opt)


if __name__ == "__main__":
    app.run(debug=True)