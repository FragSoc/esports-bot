import psycopg2
from psycopg2 import Error


class db_connection():
    def __init__(self):
        self.conn = psycopg2.connect(host="192.168.1.77",
                                        database="esportsbot",
                                        user="postgres",
                                        password="Pass2020!")
        self.cur = self.conn.cursor()

    def query(self, query):
        self.cur.execute(query)
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.close()


def add_new_vm(vc_id, guild_id, owner_id):
    db = db_connection()
    db.query(f'INSERT INTO voicemaster (vc_id, guild_id, owner_id) VALUES ({vc_id}, {guild_id}, {owner_id})')
    db.close()

#add_new_vm(8, 6, 5)