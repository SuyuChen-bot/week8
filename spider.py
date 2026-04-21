import requests
import urllib3
from bs4 import BeautifulSoup


# 隱藏不安全連線的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www1.pu.edu.tw/~tcyang/course.html"

# 加入 verify=False 忽略 SSL 驗證
Data = requests.get(url, verify=False)

# 設定編碼（預設通常是 utf-8，若抓出來是亂碼可視情況調整）
Data.encoding = "utf-8"

#print(Data.text)
sp = BeautifulSoup(Data.text, "html.parser")
result=sp.find("id=h2text")

for item in result:
	print(item)
	print()
