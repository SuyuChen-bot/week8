import requests, json
import urllib3

# 1. 關閉 SSL 警報
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"

# 2. 準備 Headers 偽裝成瀏覽器，防止伺服器強制斷線 (10054 錯誤)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    # 3. 加入 headers 並設定 verify=False
    Data = requests.get(url, headers=headers, verify=False, timeout=10)
    
    if Data.status_code == 200:
        Cond = input("請輸入欲查詢的路口關鍵字 (例如: 西屯): ")
        
        # 使用 requests 內建的 .json() 方法更簡潔
        JsonData = Data.json()
        
        count = 0
        for item in JsonData:
            if Cond in item["路口名稱"]:
                print(f"📍 {item['路口名稱']}")
                print(f"⚠️ 總共發生 {item['總件數']} 件事故")
                print("-" * 30)
                count += 1
        
        if count == 0:
            print(f"找不到包含「{Cond}」的路口資料。")
            
    else:
        print(f"無法抓取資料，伺服器回應代碼：{Data.status_code}")

except Exception as e:
    print(f"發生連線錯誤：{e}")