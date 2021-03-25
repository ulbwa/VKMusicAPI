import asyncio
import functools
import hashlib

import logging
import sys
import music_tag

from fake_headers import Headers
from os import path, makedirs, listdir
from threading import Thread
from requests import Session
from random import choice

from .results import Account, SearchResult, DownloadResult
from .cache import Cache


def asyncer(func, *args, **kwargs):
    return asyncio.get_event_loop() \
        .run_in_executor(None,
                         functools.partial(func,
                                           *args,
                                           **kwargs))


def threader(func, *args):
    return Thread(target=func, args=args)


def parse_track_data(data: dict):
    return SearchResult(
        id='{}_{}'.format(data['owner_id'], data['id']),
        artist=data['artist'],
        title=data['title'],
        duration=data['duration'],
        url=data['url'])


def gen_hash(login: str, password: str) -> str:
    return hashlib.md5(
        '{}:{}'.format(login, password).encode()
    ).hexdigest()


def gen_headers() -> dict:
    headers = Headers(
        browser="chrome",
        os="android",
        headers=True
    ).generate()
    device = choice(["Google Pixel 4 XL", "Google Pixel 3 XL", "Google Pixel 2 XL", "Google Pixel XL",
                     "Google Pixel 4", "Google Pixel 3", "Google Pixel 2", "Google Pixel",
                     "Google Pixel 3a XL", "Google Pixel 4a XL", "Google Pixel 5", "Google Pixel 3a",
                     "Google Pixel 4a", "SM-A205U", "SM-A102U", "SM-G960U", "SM-N960U", "LM-Q720",
                     "LM-X420", "LM-Q710(FGN)", "LG-M255", "SM-G960F Build/R16NW", "SM-G892A Build/NRD90M",
                     "SM-G930VC Build/NRD90M", "Nexus 6P Build/MMB29P", "G8231 Build/41.2.A.0.219",
                     "E6653 Build/32.2.A.0.253", "HTC One X10 Build/MRA58K", "HTC One M9 Build/MRA58K",
                     "Pixel C Build/NRD90M", "SGP771 Build/32.2.A.0.253", "SHIELD Tablet K1 Build/MRA58K",
                     "SM-T827R4 Build/NRD90M", "SAMSUNG SM-T550 Build/LRX22G",
                     "KFTHWI Build/KTU84M", "LG-V410/V41020c Build/LRX22G"])

    resolution = choice(["2160*1080", "1920*1080", "2560*1440", "2960*1440", "2280*1080", "1440*720",
                         "1380*720", "2960*1440"])
    android = choice([6, 7, 8, 9, 10, 11, "8.0.0", "7.1", "5.1"])
    headers['User-Agent'] = f'VKAndroidApp/6.11-6073 (Android {android}; SDK 29; ' \
                            f'armeabi-v7a; {device}; ru; {resolution})'

    return headers


class VKMusic:
    def __init__(self, accounts: [Account],
                 comment: str = 'Music',
                 proxy: str = None) -> None:
        logger_handler = logging.FileHandler(path.join(path.dirname(path.abspath(__file__)), "text.log"), "a",
                                             encoding="UTF8")
        logger_handler.setFormatter(logging.Formatter('%(asctime)-s %(levelname)s [%(name)s]: %(message)s'))

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(logger_handler)

        self.logger.info('Initialization...')

        self.api = "https://api.vk.com/method/"
        self.session = Session()
        self.session.headers = gen_headers()
        self.session.proxies = proxy
        self.accounts = list()
        self.cache = Cache(path.join(path.dirname(path.abspath(__file__)), "cache.sqlite3"))

        self.api_version = '5.90'
        self.client_id = 2274003
        self.client_secret = "hHbZxrka2uZ6jB1inYsH"

        for account in accounts:
            account_hash = gen_hash(account.login, account.password)
            try:
                if not self.cache.token_exists(account_hash):
                    token = self.get_token(account)
                    token['login'] = account.login
                    token['password'] = account.password
                    self.cache.set_token(account_hash, token)
                else:
                    token = self.cache.get_token(account_hash)

                profile = self.request('account.getProfileInfo', params={
                    "access_token": token["access_token"],
                    "v": self.api_version
                })

                self.logger.info(
                    'Account loaded: {} {} ({})'.format(profile['first_name'],
                                                        profile['last_name'],
                                                        token['user_id']))

                self.accounts.append({"access_token": token['access_token'],
                                      "user_id": token['user_id'],
                                      "login": token['login'],
                                      "password": token['password']})
            except (ValueError, KeyError):
                self.cache.del_token(account_hash)
                self.logger.warning(
                    'Authentication failed: {} {}'.format(account.login,
                                                          account.password))
                continue

        if not self.accounts:
            self.logger.error('')
        self.tracks_path = path.join(path.dirname(path.abspath(__file__)), "tracks")
        self.comment = comment

        self.logger.info('Success!')

    def request(self, method: str, **kwargs) -> dict:
        req = self.session.get(self.api + method, headers=gen_headers(), **kwargs)
        try:
            return {} if req.status_code != 200 else req.json()['response']
        except KeyError:
            return {}

    def get_token(self, account: Account):
        req = self.session.get('https://oauth.vk.com/token',
                               params={"grant_type": "password",
                                       "client_id": self.client_id,
                                       "client_secret": self.client_secret,
                                       "username": account.login,
                                       "password": account.password,
                                       "scope": "wall,photos,docs,offline,ads,video,audio",
                                       "v": self.api_version})
        if req.status_code == 200:
            return req.json()
        else:
            raise ValueError("Invalid password")

    async def get_user_by_link(self, url: str) -> (int, False):
        if url.lower().startswith('https://vk.com/') or url.lower().startswith(
                'https://m.vk.com/') or url.lower().startswith('vk.com/') or url.lower().startswith('m.vk.com/'):
            req = await asyncer(self.request, 'users.get',
                                params={"user_ids": url.split('/')[-1],
                                        "access_token": choice(self.accounts)['access_token'],
                                        "v": self.api_version})
        else:
            return False

        if not req:
            return False

        try:
            return req[0]['id']
        except KeyError:
            return False

    async def get_user_audio(self, user_id: int):
        req = await asyncer(self.request, 'audio.get',
                            params={'count': 1000, 'offset': 0, 'owner_id': user_id,
                                    "access_token": choice(self.accounts)['access_token'],
                                    "v": self.api_version})

        if not req:
            return False

        output = list()

        for a in req['items']:
            if not await asyncer(self.cache.track_exists, '{}_{}'.format(a['owner_id'], a['id'])):
                await asyncer(self.cache.dump_audio, parse_track_data(a))
            output.append(parse_track_data(a))

        return output

    async def get_audio(self, track_id: str):
        if self.cache.track_exists(track_id):
            return [self.cache.get_audio(track_id)]

        req = await asyncer(self.request, 'audio.get',
                            params={'count': 1000, 'offset': 0, 'owner_id': track_id.split('_')[0],
                                    "audio_ids": [track_id.split("_")[-1]],
                                    "access_token": choice(self.accounts)['access_token'],
                                    "v": self.api_version})

        if not req:
            return False

        output = list()

        for a in req['items']:
            if not await asyncer(self.cache.track_exists, track_id):
                await asyncer(self.cache.dump_audio, parse_track_data(a))
            output.append(parse_track_data(a))

        return output

    async def search(self, query: str):
        req = await asyncer(self.request, 'audio.search',
                            params={'count': 100, 'q': query,
                                    "access_token": choice(self.accounts)['access_token'],
                                    "v": self.api_version})

        if not req:
            return False

        output = list()

        for a in req['items']:
            if not await asyncer(self.cache.track_exists, '{}_{}'.format(a['owner_id'], a['id'])):
                await asyncer(self.cache.dump_audio, parse_track_data(a))
            output.append(parse_track_data(a))

        return output

    async def download_audio(self, track_id: str):
        track = await self.get_audio(track_id)
        if not track:
            return False
        else:
            track = track[0]

        symbols = ' -1234567890qwertyuiopasdfghjklzxcvbnmйцукенгшщзхъфывапролджэячсмитьбю'
        name = track.artist + ' - ' + track.title
        name_list = list()
        [name_list.append(a) if a.lower() in symbols else "" for a in name]
        if len(name_list) > 35:
            name_list = name_list[:35]
            name_list.append('...')
        name_list.append(' - ')
        name_list.extend([choice('QWERTYUIOPASDFGHJKLZXCVBNM1234567890') for _ in range(3)])
        directory = path.join(self.tracks_path, "".join(name_list)) + '.mp3'

        if "tracks" not in listdir(path.dirname(path.abspath(__file__))):
            makedirs(path.join(path.dirname(path.abspath(__file__)), "tracks"))

        crypted_audio = await asyncer(self.session.get, track.url)

        if len(crypted_audio.content) == 0:
            raise Exception('Track not found')

        with open(directory, 'wb') as f:
            f.write(crypted_audio.content)

        tag = music_tag.load_file(directory)

        tag['artist'] = track.artist
        tag['tracktitle'] = track.title

        tag['genre'] = self.comment

        tag.save()

        return DownloadResult(
            id=track.id,
            title=track.title,
            artist=track.artist,
            duration=track.duration,
            file=directory
        )
