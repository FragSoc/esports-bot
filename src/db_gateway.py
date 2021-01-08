import psycopg2
import os

class db_connection():
    def __init__(self):
        self.conn = psycopg2.connect(host=os.getenv('PG_HOST'),
                                        database=os.getenv('PG_DATABASE'),
                                        user=os.getenv('PG_USER'),
                                        password=os.getenv('PG_PWD'))
        self.cur = self.conn.cursor()

    def commit_query(self, query):
        self.cur.execute(query)
        self.conn.commit()

    def return_query(self, query):
        self.cur.execute(query)
        columns = [desc[0] for desc in self.cur.description]
        real_dict = [dict(zip(columns, row)) for row in self.cur.fetchall()]
        self.conn.commit()
        return real_dict

    def close(self):
        self.cur.close()
        self.conn.close()

class db_gateway():
    
    @staticmethod
    def get_param_insert_str(params):
        key_string = str()
        val_string = str()
        for key, val in params.items():
            key_string += f'{key}, '
            val_string += f'{val}, '
        return (key_string[:-2], val_string[:-2])
    
    @staticmethod
    def get_param_select_str(params):
        key_val_string = str()
        for key, val in params.items():
            key_val_string += f"{key}='{val}' AND "
        return key_val_string[:-5]

    def insert(self, table, params):
        # Example usage:
        # db_gateway().insert('voicemaster', params={'guild_id': '11111131111111111',
        #                                     'owner_id': '222222222222222222',
        #                                     'channel_id': '333333333333333333'
        #                                     })
        try:
            db = db_connection()
            query_vals = self.get_param_insert_str(params)
            query_string = f'INSERT INTO {table}({query_vals[0]}) VALUES ({query_vals[1]})'
            db.commit_query(query_string)
            db.close()
            return True
        except Exception as err:
            raise RuntimeError('Error occurred using INSERT') from err
        
    def get(self, table, params):
        # Example usage:
        # returned_val = db_gateway().get('voicemaster', params={
        #                                     'channel_id': '333333333333333333'
        #                                     })
        try:
            db = db_connection()
            query_string = f'SELECT * FROM {table} WHERE {self.get_param_select_str(params)}'
            returned_data = db.return_query(query_string)
            db.close()
            return returned_data
        except Exception as err:
            raise RuntimeError('Error occurred using SELECT') from err