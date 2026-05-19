import os
import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import urllib3
from flask import Flask, render_template, request, jsonify, make_response
import firebase_admin
from firebase_admin import credentials, firestore

# 關閉 InsecureRequestWarning 警告 (統一放置於頂部)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== Firebase 初始化 (確保只執行一次) ====================
if not firebase_admin._apps:
    if os.path.exists('serviceAccountKey.json'):
        # 本地環境：讀取檔案
        cred = credentials.Certificate('serviceAccountKey.json')
    else:
        # 雲端環境：從環境變數讀取 JSON 字串
        firebase_config = os.getenv('FIREBASE_CONFIG')
        if firebase_config:
            cred_dict = json.loads(firebase_config)
            cred = credentials.Certificate(cred_dict)
        else:
            raise ValueError("找不到 Firebase 設定，請確認環境變數 FIREBASE_CONFIG")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==================== Flask App 初始化 ====================
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
    link += "<a href=/webhook>聊天機器人<a><hr>"
    return link

# ==================== 機器人 Webhook 1 (第一個) ====================
@app.route("/webhook", methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    target_rate = req.get("queryResult", {}).get("parameters", {}).get("rate")

    if not target_rate:
        return jsonify({"fulfillmentText": "陳素宥您好，我沒有收到正確的分級參數喔。"})

    movies_ref = db.collection("本週新片含分級")
    docs = movies_ref.where("rate", "==", target_rate).get()
    
    movie_list = []
    for doc in docs:
        m = doc.to_dict()
        if m.get("title"):
            movie_list.append(m.get("title"))

    if movie_list:
        reply = f"陳素宥您好！為您查詢到本週上映的 {target_rate} 電影有：\n"
        reply += "、".join(movie_list)
    else:
        reply = f"陳素宥您好，目前資料庫中沒有找到符合 {target_rate} 的電影喔。"

    return jsonify({"fulfillmentText": reply})

# ==================== 機器人 Webhook 3 (第二個，名稱已徹底分開) ====================
@app.route("/webhook3", methods=["POST"])
def webhook3():
    req = request.get_json(force=True)
    action = req.get("queryResult").get("action")
    info = "未觸發正確的 action 動作"
    
    if (action == "rateChoice"):
        rate = req.get("queryResult").get("parameters").get("rate")
        info = "我是楊子青開發的電影聊天機器人,您選擇的電影分級是：" + rate + "，相關電影：\n"
        
        db_client = firestore.client()
        collection_ref = db_client.collection("本週新片含分級")
        docs = collection_ref.get()
        result = ""
        
        for doc in docs:
            movie_dict = doc.to_dict()
            movie_rate = movie_dict.get("rate", "")
            movie_title = movie_dict.get("title", "")
            movie_link = movie_dict.get("hyperlink", "")
            
            if rate in movie_rate:
                result += "片名：" + movie_title + "\n"
                result += "介紹：" + movie_link + "\n\n"
        
        if result == "":
            result = "目前資料庫中沒有此分級的電影喔。\n"
            
        info += result
        
    return make_response(jsonify({"fulfillmentText": info}))

# ==================== 本週新片爬蟲路由 ====================
@app.route("/rate")
def rate():
    url = "https://www.atmovies.com.tw/movie/new/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        Data = requests.get(url, headers=headers, verify=False, timeout=10)
        Data.encoding = "utf-8"
        sp = BeautifulSoup(Data.text, "html.parser")
        
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

            r_tag = x.find(class_="runtime").find("img")
            rate_label = "未分級"
            if r_tag:
                rr = r_tag.get("src").replace("/images/cer_", "").replace(".gif", "")
                mapping = {"G": "普遍級", "P": "保護級", "F2": "輔12級", "F5": "輔15級", "R": "限制級"}
                rate_label = mapping.get(rr, "限制級")

            t_text = x.find(class_="runtime").text
            showLength = "0"
            showDate = "未知"
            if "片長" in t_text:
                showLength = t_text[t_text.find("片長")+3 : t_text.find("分")]
            if "上映日期" in t_text:
                rawDate = t_text[t_text.find("上映日期")+5 : t_text.find("上映廳數")-8].strip()
                try:
                    date_obj = datetime.strptime(rawDate, "%m/%d/%Y")
                    showDate = date_obj.strftime("%Y/%m/%d")
                except:
                    showDate = rawDate

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

            db.collection("本週新片含分級").document(movie_id).set(doc)
            count += 1

        return f"<h2>成功！</h2>已爬取 {count} 部新片，存檔至「本週新片含分級」集合。<br>網站更新日期：{lastUpdate}<br><br><a href='/'>回首頁</a>"
    except Exception as e:
        return f"<h2>爬取失敗</h2>錯誤訊息：{e}<br><a href='/'>回首頁</a>"

# ==================== 其他既有路由 ====================
@app.route("/weather", methods=["GET", "POST"])
def weather():
    city = request.values.get("city")
    form_html = """
    <h2>縣市天氣查詢</h2>
    <form action="/weather" method="POST">
        <input type="text" name="city" placeholder="請輸入縣市名稱" value="{val}">
        <button type="submit">查詢</button>
    </form>
    <hr>
    """.format(val=city if city else "")

    if not city:
        return form_html + "請輸入縣市名稱進行查詢。<br><br><a href='/'>回首頁</a>"

    city = city.replace("台", "臺")
    token = os.getenv('CWA_TOKEN', 'rdec-key-123-45678-011121314') 
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={token}&format=JSON&locationName={city}"

    try:
        Data = requests.get(url, verify=False, timeout=10) 
        JsonData = Data.json()
        if "records" in JsonData and JsonData["records"].get("location"):
            Weather = JsonData["records"]["location"][0]["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
            Rain = JsonData["records"]["location"][0]["weatherElement"][1]["time"][0]["parameter"]["parameterName"]
            result_msg = f"<h3>{city} 的天氣是：{Weather}，降雨機率：{Rain}%</h3>"
        else:
            result_msg = f"<h3>找不到「{city}」的天氣資料，請確認輸入是否正確。</h3>"
    except Exception as e:
        result_msg = f"<h3>查詢失敗：{str(e)}</h3>"
    
    return form_html + result_msg + "<br><a href='/'>回首頁</a>"

@app.route("/road")
def get_road_data():
    url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
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
        return f"<h3>目前無法連線至政府資料庫</h3>錯誤原因：{str(e)}<br><br><a href='/'>回首頁</a>"

@app.route("/movie3", methods=["GET", "POST"])
def movie3():
    keyword = request.values.get("keyword")
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
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0"}
    blacklist = ["電影首頁", "本期二輪", "電影", "List All", "本周新片", "本期首輪", "近期上映", "新片快報", "票房排行榜", "資料館"]
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0

    try:
        data = requests.get(url, headers=headers, timeout=10)
        data.encoding = "utf-8"
        sp = BeautifulSoup(data.text, "html.parser")
        links = sp.find_all("a")
        
        for link in links:
            href = link.get("href")
            title = link.text.strip()
            if href and "/movie/" in href and len(title) > 1:
                if title not in blacklist and not any(word in title for word in ["電影首頁", "List All"]):
                    clean_title = re.sub(r'^(\d{4}/)?\d{1,2}/\d{1,2}\s*', '', title)
                    if clean_title and clean_title not in blacklist:
                        full_url = "http://www.atmovies.com.tw" + href
                        doc_ref = db.collection("UpcomingMovies").document(clean_title)
                        doc_ref.set({"name": clean_title, "url": full_url, "update": update_time})
                        count += 1
        if count > 0:
            return f"<h2>近期上映電影已爬蟲及存檔完畢</h2>最近更新日期為：{update_time}<br><br><a href='/'>回首頁</a>"
        else:
            return f"<h2>更新完成，但沒有抓到新電影。</h2><br><a href='/'>回首頁</a>"
    except Exception as e:
        return f"<h2>執行失敗</h2>錯誤訊息：{e}<br><br><a href='/'>回首頁</a>"

@app.route("/movie")
def movie():
    R = "<h2>開眼即將上映電影</h2>"
    url = "http://www.atmovies.com.tw/movie/next/"
    headers = {"User-Agent": "Mozilla/5.0"}
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
            if href and "/movie/" in href and len(title) > 1:
                if title not in blacklist and not any(word in title for word in ["電影首頁", "List All"]):
                    clean_title = re.sub(r'^(\d{4}/)?\d{1,2}/\d{1,2}\s*', '', title)
                    if clean_title and clean_title not in blacklist:
                        full_url = "http://www.atmovies.com.tw" + href
                        if clean_title not in [m['name'] for m in movie_list]:
                            movie_list.append({"name": clean_title, "url": full_url})

        for m in movie_list:
            R += f"電影名稱：{m['name']}<br>"
            R += f"連結：<a href='{m['url']}' target='_blank'>{m['url']}</a><br><hr>"
    except Exception as e:
        R += f"發生錯誤：{e}"
    R += "<br><a href='/'>回首頁</a>"
    return R

@app.route("/sp1")
def sp1():
    R = "<h2>關於網頁內容爬取</h2>"
    url = "https://www1.pu.edu.tw/~tcyang/course.html" 
    try:
        Data = requests.get(url, verify=False, timeout=10)
        Data.encoding = "utf-8"
        sp = BeautifulSoup(Data.text, "html.parser")
        result = sp.select("td a")
        for item in result:
            R += f"連結文字: {item.text}<br>"
            R += f"網址: {item.get('href')}<br><br>"
    except Exception as e:
        R += f"抓取失敗：{e}"
    R += "<br><a href='/'>回首頁</a>"
    return R

@app.route("/search")
def search():
    collection_ref = db.collection("靜宜資管2026a")
    keyword = request.values.get("keyword")
    form_html = """
    <h2>靜宜資管老師查詢</h2>
    <form action="/search" method="GET">
        <input type="text" name="keyword" placeholder="請輸入老師名字" value="{val}">
        <button type="submit">搜尋</button>
    </form>
    <hr>
    """.format(val=keyword if keyword else "")

    if not keyword:
        return form_html + "請輸入關鍵字進行搜尋。<br><br><a href='/'>回首頁</a>"

    docs = collection_ref.order_by("lab").get()
    Temp = ""
    found_count = 0
    for doc in docs:
        user = doc.to_dict()
        user_name = user.get("name", "")
        if keyword in user_name:
            Temp += f"名字: {user_name}, Lab: {user.get('lab')}<br>"
            found_count += 1

    result_msg = f"<h3>關鍵字「{keyword}」的搜尋結果如下：</h3>" if found_count > 0 else f"<h3>搜尋結果：</h3>找不到包含「{keyword}」的資料。"
    return form_html + result_msg + Temp + "<br><br><a href='/'>回首頁</a>"

@app.route("/read")
def read():
    Temp = ""
    collection_ref = db.collection("靜宜資管2026a")
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
    now_str = f"{now.year}年{now.month}月{now.day}日"
    return render_template("today.html", datetime=now_str)

@app.route("/about")
def about():
    return render_template("MIS2A7.html")

@app.route("/welcome", methods=["GET"])
def welcome():
    x = request.values.get("u")
    y = request.values.get("dep")
    return render_template("welcome.html", name=x, dep=y)

@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        user = request.form.get("user", "")
        pwd = request.form.get("pwd", "")
        return f"您輸入的帳號是：{user}; 密碼為：{pwd}"
    return render_template("account.html")

@app.route('/math', methods=['GET', 'POST'])
def math():
    Result = None
    error_msg = None
    x, y, opt = None, None, None

    if request.method == 'POST':
        try:
            x = int(request.form.get('x'))
            y = int(request.form.get('y'))
            opt = request.form.get('opt')
            if opt == "/" and y == 0:
                error_msg = "錯誤：除數不能為 0"
            else:
                match opt:
                    case "+": Result = x + y
                    case "-": Result = x - y
                    case "*": Result = x * y
                    case "/": Result = x / y
                    case "%": Result = x % y
        except:
            error_msg = "請輸入有效的數字"
    return render_template('math.html', Result=Result, error_msg=error_msg, x=x, y=y, opt=opt)

# 針對 Vercel Serverless 環境的 handler 設定
app = app

if __name__ == "__main__":
    app.run(debug=True)