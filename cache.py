import sqlite3
from json import dumps, loads

from .results import SearchResult
from datetime import datetime
from threading import Thread
from time import sleep


class Cache:
    def __init__(self, database_name: str) -> None:
        self.database_name = database_name
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        try:
            cursor.execute(
                'CREATE TABLE accounts ('
                'hash TEXT, user_id INTEGER, '
                'access_token TEXT, login TEXT,'
                'password TEXT)')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute(
                'CREATE TABLE tracks ('
                'id TEXT, artist TEXT, '
                'title TEXT, duration INTEGER,'
                'url TEXT, delete_time INTEGER)')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute(
                'CREATE TABLE users ('
                'id INTEGER, audios TEXT, '
                'delete_time INTEGER)')
        except sqlite3.OperationalError:
            pass

        connection.close()

        Thread(target=self.deleter).start()

    def deleter(self):
        while True:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()
            sleep(3600)
            try:
                cursor.execute('DELETE FROM tracks WHERE delete_time < %s;',
                               (int(datetime.utcnow().timestamp()),))
            except Exception as error:
                print("Error in transction Reverting all other operations of a transction ", error)
            connection.close()

    def get_token(self, account_hash: str) -> dict:
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('SELECT * FROM accounts WHERE hash = (?)',
                       (account_hash,))
        fetch = cursor.fetchone()
        connection.close()

        return {"access_token": fetch[2],
                "user_id": fetch[1],
                "login": fetch[3],
                "password": fetch[4]}

    def set_token(self, account_hash: str, request_data: dict) -> None:
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('INSERT INTO accounts ('
                       'hash, user_id, access_token, '
                       'login, password) VALUES(?, ?, ?, ?, ?)',
                       (account_hash, request_data['user_id'],
                        request_data['access_token'],
                        request_data['login'],
                        request_data['password']))

        connection.commit()
        connection.close()

    def del_token(self, account_hash: str) -> None:
        try:
            connection = sqlite3.connect(self.database_name)
            cursor = connection.cursor()

            cursor.execute('DELETE FROM accounts WHERE hash = (?)',
                           (account_hash,))

            connection.commit()
            connection.close()
        except sqlite3.OperationalError:
            pass

    def token_exists(self, account_hash: str) -> bool:
        try:
            self.get_token(account_hash)
            return True
        except TypeError:
            return False

    def dump_audio(self, data: SearchResult):
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('INSERT INTO tracks ('
                       'id, artist, title, duration, url, delete_time)'
                       ' VALUES(?, ?, ?, ?, ?, ?)',
                       (data.id, data.artist, data.title,
                        data.duration, data.url,
                        datetime.utcnow().timestamp() + 3600))

        connection.commit()
        connection.close()

    def get_audio(self, track_id: str):
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('SELECT * FROM tracks WHERE id = (?)',
                       (track_id,))
        fetch = cursor.fetchone()
        connection.close()

        return SearchResult(id=fetch[0],
                            artist=fetch[1],
                            title=fetch[2],
                            duration=fetch[3],
                            url=fetch[4])

    def track_exists(self, track_id: str) -> bool:
        try:
            self.get_audio(track_id)
            return True
        except TypeError:
            return False

    def set_user_audios(self, user_id: int, tracks: list):
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('INSERT INTO users ('
                       'id, audios, delete_time) '
                       'VALUES(?, ?, ?)',
                       (user_id, dumps(tracks),
                        datetime.utcnow().timestamp() + 3600))

        connection.commit()
        connection.close()

    def get_user_audios(self, user_id: int):
        connection = sqlite3.connect(self.database_name)
        cursor = connection.cursor()

        cursor.execute('SELECT audios FROM users WHERE id = (?)',
                       (user_id,))
        fetch = loads(cursor.fetchone()[0])
        connection.close()

        return fetch

    def user_exists(self, user_id: int):
        try:
            self.get_user_audios(user_id)
            return True
        except TypeError:
            return False
