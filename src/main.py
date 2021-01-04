import psycopg2
conn = psycopg2.connect(
    host="192.168.1.77",
    database="esportsbot",
    user="postgres",
    password="Pass2020!")

cur = conn.cursor()
cur.execute('SELECT * FROM voicemaster')
print(cur.fetchall())

# counter = 0
# while True:
#     print(f"LIVE: {counter}")
#     counter += 1