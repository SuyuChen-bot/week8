import requests, json
import urllib3

# 1. 關閉 SSL 警報訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 這裡必須定義變數，否則會出現 NameError ---
token = "CWA-你的授權碼"  # 請至氣象署官網申請並貼上
city = "臺中市"          # 記得使用「臺」字

# 2. 組合網址
url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={token}&format=JSON&locationName={city}"

# 3. 執行請求
try:
    # 加入 verify=False 解決 SSL 問題
    Data = requests.get(url, verify=False, timeout=10)
    
    if Data.status_code == 200:
        JsonData = Data.json()
        
        # 解析範例：取出縣市名稱與預報描述
        location = JsonData["records"]["location"][0]["locationName"]
        desc = JsonData["records"]["datasetDescription"]
        
        print(f"成功取得 {location} 的資料！")
        print(f"資料描述：{desc}")
    else:
        print(f"錯誤代碼：{Data.status_code}")
        print("請檢查 Token 是否正確，或 API 網址是否有誤。")
        
except Exception as e:
    print(f"連線失敗：{e}")