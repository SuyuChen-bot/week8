import requests, json
import urllib3

# 關閉 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

city = input("請輸入縣市：")
city = city.replace("台","臺")
token = "rdec-key-123-45678-011121314"
url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=" + token + "&format=JSON&locationName=" + str(city)

# 加入 verify=False 參數
Data = requests.get(url, verify=False) 

# 以下兩行可以隱藏「不安全請求」的警告訊息（選填）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JsonData = json.loads(Data.text)
Weather = JsonData["records"]["location"][0]["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
Rain = JsonData["records"]["location"][0]["weatherElement"][1]["time"][0]["parameter"]["parameterName"]

print(f"{city} 的天氣是：{Weather}，降雨機率：{Rain}%")