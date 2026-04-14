def square(y):
	print(f"{y * (y+1) // 2}")



x = int(input("請輸入一個正整數："))

for i in range(1,x+1):
	square(i)