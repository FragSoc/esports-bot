import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import traceback


class db_connection():
    def __init__(self, database=None):
        self.conn = psycopg2.connect(host=os.getenv('PG_HOST'),
                                     database=os.getenv(
                                         'PG_DATABASE') if database is None else database,
                                     user=os.getenv('PG_USER'),
                                     password=os.getenv('PG_PWD'))
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
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
            key_string += f"{key}, "
            val_string += f"'{val}', "
        return (key_string[:-2], val_string[:-2])

    @staticmethod
    def get_param_select_str(params):
        key_val_string = str()
        for key, val in params.items():
            if val == 'NULL':
                key_val_string += f"{key}={val} AND "
            else:
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
            traceback.print_exc()
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
            traceback.print_exc()
            raise RuntimeError('Error occurred using SELECT') from err

    def getall(self, table):
        # Example usage:
        # returned_val = db_gateway().getall('voicemaster')
        try:
            db = db_connection()
            query_string = f'SELECT * FROM {table}'
            returned_data = db.return_query(query_string)
            db.close()
            return returned_data
        except Exception as err:
            traceback.print_exc()
            raise RuntimeError('Error occurred using SELECT ALL') from err

    def update(self, table, set_params, where_params):
        # Example usage:
        # db_gateway().update('loggingchannel', set_params={'guild_id': '44'}, where_params={'channel_id': '795761577705078808'})
        try:
            db = db_connection()
            query_string = f'UPDATE {table} SET {self.get_param_select_str(set_params)} WHERE {self.get_param_select_str(where_params)}'
            db.commit_query(query_string)
            db.close()
            return True
        except Exception as err:
            traceback.print_exc()
            raise RuntimeError('Error occurred using UPDATE') from err

    def delete(self, table, where_params):
        # Example usage:
        # db_gateway().delete('loggingchannel', where_params={'guild_id': 44})
        try:
            db = db_connection()
            query_string = f'DELETE FROM {table} WHERE {self.get_param_select_str(where_params)}'
            db.commit_query(query_string)
            db.close()
            return True
            # return query_string
        except Exception as err:
            traceback.print_exc()
            raise RuntimeError('Error occurred using DELETE') from err

    def pure_return(self, sql_query, database=None):
        # Example usage:
        # db_gateway().pure("SELECT * FROM 'guild_info'"")
        try:
            db = db_connection(database)
            returned_data = db.return_query(sql_query)
            db.close()
            return returned_data
        except Exception as err:
            traceback.print_exc()
            raise RuntimeError('Error occurred using PURE') from err

    def pure_query(self, sql_query, database=None):
        # Example usage:
        # db_gateway().pure('SELECT * FROM 'guild_info'')
        try:
            db = db_connection(database)
            returned_data = db.commit_query(sql_query)
            db.close()
            return returned_data
        except Exception as err:
            traceback.print_exc()
            raise RuntimeError('Error occurred using PURE') from err
