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
    return link


import re  # 記得在檔案最上方加入這行

import re

import re

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