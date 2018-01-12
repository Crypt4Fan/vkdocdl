#!/usr/bin/python3

# Скрипт для поиска и загрузки документов vk.com
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser
from datetime import date, timedelta
import json
from pathlib import Path
from time import time, ctime
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
import webbrowser


BANNER = '''
__     ___    ____             ____  _     
\ \   / / | _|  _ \  ___   ___|  _ \| |    
 \ \ / /| |/ / | | |/ _ \ / __| | | | |    
  \ V / |   <| |_| | (_) | (__| |_| | |___ 
   \_/  |_|\_\____/ \___/ \___|____/|_____|                                           
'''
DESC = 'Documents downloader for vk.com'
# Директория для сохранения результатов поиска 
LOOT_DIR = './loot/'
# Файл с настройками
SETTINGS_FILENAME = 'settings.ini'


# Функция для получения настроек,
# возвращает токен пользователя
def getUserSettings():
    # Получение id приложения
    app_id = input('Enter your vk application id: ')
    # Получение токена
    params = {
        'client_id': app_id,
        'display': 'page',
        'redirect_uri': 'https://oauth.vk.com/blank.html',
        'scope': 'docs,offline',
        'response_type': 'token',
        'v': 5.68
    }
    url = 'https://oauth.vk.com/authorize?{}'.format(urlencode(params))
    print('Paste your access token there: ', end='')
    webbrowser.open(url)
    token = input()
    # Сохранение настроек
    print('Saving your application id and token in {}'.format(SETTINGS_FILENAME))
    config = ConfigParser()
    config.add_section('SETTINGS')
    config.set('SETTINGS', 'app_id', app_id)
    config.set('SETTINGS', 'user_token', token)
    settings_path = Path(SETTINGS_FILENAME)
    with settings_path.open(mode='w') as sfile:
        config.write(sfile)
    return token


# Класс документа
class Doc:

    def __init__(self, data):
        # id файла
        self.id = data['id']
        # id владельца файла
        self.owner_id = data['owner_id']
        # Название файла
        self.title = data['title']
        # Размер файла в байтах
        self.size = data['size']
        # Расширение файла
        self.ext = data['ext']
        # URL для загрузки файла
        self.url = data['url']
        # Дата добавления файла
        self.add_date = data['date']
    
    def __str__(self):
        return '\nTitle: {title}\nId: {id}\nOwner: {owner}\n\
Date of add: {add_date}\nSize: {B} Bytes|{KB} KB|{MB} MB'.format(
            title=self.title,
            id=self.id,
            owner=self.owner_id,
            add_date=date.fromtimestamp(self.add_date),
            B=self.size,
            KB=round(self.size/(2**10), 2),
            MB=round(self.size/(2**20), 2)
        )

    # Функция сохранения файла на диск
    def download(self):
        # Имя файла в формате "id файла"_"id владельца"_"название файла"
        filename = '{id}_{owner}_{title}'.format(
            id=self.id,
            owner=self.owner_id,
            title=self.title
        )
        try:
            data = urlopen(self.url).read()
        except Exception:
            raise Exception('Some error while downloading {}'.format(filename))
        Path(LOOT_DIR+filename).write_bytes(data)
        return 'Saved {}'.format(filename)


# Функция поиска документов
# Аргументы: query - строка для поиска,
# token - пользовательский токен
# Возвращает: список объектов Doc
def searchDocs(query, token):
    params = {
        'q': query,
        'count': 1000,
        'access_token': token,
        'v': 5.68
    }
    url = 'https://api.vk.com/method/docs.search?{}'.format(urlencode(params))
    response = urlopen(url)
    data = json.loads(response.read().decode())
    # В случае получения ошибки авторизации требуется удалить файл с
    # настройками и перезапусить скрипт
    if 'error' in data and data['error']['error_code'] == 5:
        print('Invalid user token. Try to get new. Delete {} and restart.'.format(SETTINGS_FILENAME))
        exit(1)
    else:
        docs = [Doc(item) for item in data['response']['items']]
        return docs


# Функция для вывода общей информации о результатах поиска
def printTotalInfo(docs):
    total_size = sum([doc.size for doc in docs])
    print('\nTotal files: {nfiles}\nTotal size: {B} Bytes|{KB} KB|{MB} MB|{GB} GB'.format(
        nfiles=len(docs),
        B=total_size,
        KB=round(total_size/(2**10), 2),
        MB=round(total_size/(2**20), 2),
        GB=round(total_size/(2**30), 2)
    ))


# Функция загрузки найденых файлов в несколько потоков
# Аргументы: docs - список объктов Doc,
# nthreads - число потоков
def downloadDocs(docs, nthreads):
    with ThreadPoolExecutor(max_workers=nthreads) as executor:
        futures = [executor.submit(doc.download) for doc in docs]
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                print(e)


# Функция обработки аргументов командной строки
def parseArgs():
    args_parser = ArgumentParser(description=DESC)
    # Опция сохранения найденых файлов,
    # по-умолчанию файлы не сохраняются
    args_parser.add_argument(
        '-s', '--save',
        help='save found files',
        action='store_true'
    )
    # Опция, задающая расширение файлов,
    # по-умолчанию ищем файлы с любым расширением
    args_parser.add_argument(
        '-e', '--ext',
        help='file extensions for search',
        action='append',
        default=[]
    )
    # Кол-во потоков при скачивании файлов,
    # по-умолчанию 4
    args_parser.add_argument(
        '-t', '--threads',
        help='number of threads for downloading files',
        default=4,
        type=int
    )
    # Обязательный аргумент, строка с поисковым запросом
    args_parser.add_argument(
        'query',
        help='search query'
    )
    return args_parser.parse_args()


def main():
    print(BANNER)
    # Парсим аргументы командной строки
    args = parseArgs()
    # Проверяем наличие директории для загруженных файлов,
    # если директории нет, создаем
    print('Checking of existing a dir for loot')
    loot_path = Path(LOOT_DIR)
    if not loot_path.exists() or not loot_path.is_dir():
        loot_path.mkdir()
    print('OK')
    # Проверка на наличие файла с пользовательским токеном,
    # если файла нет, создаем. Если файл существует, читаем
    # из него токен.
    print('Getting token')
    settings_path = Path(SETTINGS_FILENAME)
    if not settings_path.exists():
        token = getUserSettings()
    else:
        config = ConfigParser()
        with settings_path.open() as sfile:
            config.read_file(sfile)
        token = config.get('SETTINGS', 'user_token')
    print('ОК')
    # Ищем файлы
    print('Searching...')
    docs = searchDocs(args.query, token)
    # Фильтруем файлы по расширениям заданным опцией --ext
    if args.ext:
        docs = list(filter(lambda doc: doc.ext in args.ext, docs))
    # Сортируем файлы по дате добавления, самые свежие в начале
    docs.sort(key=lambda doc: doc.add_date, reverse=True)
    # Вывод информации о найденых файлах
    for doc in docs:
        print(doc)
    printTotalInfo(docs)
    # Загрузка файлов
    if args.save:
        start = time()
        print('\nStart downloading of found files at: {}'.format(ctime(start)))
        downloadDocs(docs, args.threads)
        finish = time()
        print('Finish at: {done}. Total time: {ttime}'.format(
            done=ctime(finish),
            ttime=timedelta(seconds=finish-start)
        ))


if __name__ == '__main__':
    main()
