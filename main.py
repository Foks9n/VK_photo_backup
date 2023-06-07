import json
import requests
from tqdm import tqdm
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os

class VK:
    def __init__(self, user_id, token, yandex_token):
        self.token = token
        self.yandex_token = yandex_token
        self.user_id = user_id

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'OAuth {self.token}'
        }

    def select_album(self):
        '''
        Данная программа выводит список доступных альбомов для резервного корирования.
        '''
        VK_url = "https://api.vk.com/method/photos.getAlbums"
        params = {
            "access_token": self.token,
            "owner_id": self.user_id,
            "need_system": 1,
            "need_covers": 1,
            "photo_sizes": 1,
            "v": "5.131"
        }
        response = requests.get(VK_url, params=params)
        data = response.json()
        albums = data['response']['items']
        print("Доступные альбомы:")
        for i, album in enumerate(albums):
            print(f"{i + 1}. {album['title']} (id: {album['id']})")

        album_index = input("Введите id альбома для резервного копирования фотографий: ")
        try:
            album_index = int(album_index)
            if album_index < 1 or album_index > len(albums):
                print("Неверный номер альбома.")
                return None
            selected_album = albums[album_index - 1]
            return selected_album
        except ValueError:
            print("Неверный номер альбома.")
            return None

    def get_photo(self, album_id, count=5):
        '''
        Программа запрашивает данные о фотографиях в нужном альбоме.
        На вход передается id альбома для резервного копирования и колличество фотографий, которое нам необходимо.
        Возвращает данные в формате JSON
        '''
        url = 'https://api.vk.com/method/photos.get'
        headers = self.get_headers()
        params = {'owner_id': self.user_id,
                  'access_token': token,
                  'album_id': album_id,
                  'extended': 1,
                  'photos_sizes': 1,
                  'count': count,
                  'v': '5.131'
                  }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        photos = data['response']['items']
        return photos

    def write(self):
        '''
        Программа записывает информацию о копируемых фотографиях, также загружает на Яндекс диск и Google Drive.
        В начале вызывается метод выбора альбома из которого необходимо сделать резервную копию
        После проходит авторизация в Google Drive API.
        Создаются папки в облачных хранилищах.
        Затем запрашиваются данные о фотографиях в нужном альбоме VK.
        Производится загрузка данных на облачные хранилища, а также записывается JSON файл с информацией о фотографиях.
        В процессе выполнения загрузки и записи данных выводится логирование, информирующее о состоянии загрузки,
        прогресс выполнения программы дублируется посредством библиотеки tqdm.
        '''

        album = self.select_album()

        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        drive = GoogleDrive(gauth)

        if not album:
            print('Нет доступных альбомов для резервного копирования фотографий.')
            return

        folder_path = f"VK_Backup_album_{album['id']}"
        print(album['id'])

        folder_id = self.create_folder_on_google_drive(drive, folder_path)

        self.create_folder_on_yandex_disk(folder_path)

        result = self.get_photo(album['id'])

        photos_data = []

        with tqdm(total=len(result), desc='Выполняется резервное копирование') as res:
            for text in result:
                likes = text['likes']['count']
                for txt in text['sizes']:
                    if txt['type'] == 'w':
                        photos_data.append({
                            "file_name": f"{likes}_{text['id']}.jpg",
                            "size": txt['type']
                        })
                        self.download_photo(txt['url'], f"{likes}_{text['id']}.jpg")
                        self.upload_photo_yandex_disk(f"{likes}_{text['id']}.jpg", folder_path)
                        self.upload_photo_to_google_drive(drive, f"{likes}_{text['id']}.jpg", folder_id)
                        break
                    elif txt['type'] == 'z':
                        photos_data.append({
                            "file_name": f"{likes}_{text['id']}.jpg",
                            "size": txt['type']
                        })
                        self.download_photo(txt['url'], f"{likes}_{text['id']}.jpg")
                        self.upload_photo_yandex_disk(f"{likes}_{text['id']}.jpg", folder_path)
                        self.upload_photo_to_google_drive(drive, f"{likes}_{text['id']}.jpg", folder_id)
                res.update(1)

        file_name = f"{album['id']}_VK_photos.json"
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(photos_data, f)

    def download_photo(self, photo_url, file_name):
        '''
        Загрузка фотографии по URL и сохранение на диск
        '''
        response = requests.get(photo_url)
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"Фотография '{file_name}' загружена для дальнейшей обработки.")

    def create_folder_on_google_drive(self, drive, folder_path):
        '''
        Метод создает папку на Google Drive для хранения резервной копии фотографий.
        Если папка уже существует, выводится соответствующее сообщение.
        На вход подаются данные об авторизации и необходимое название папки.
        Возвращается информация о результате создания папки.
        '''
        folder_id = None
        folder_name = os.path.basename(folder_path)
        folder_exists = False

        file_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
        for file in file_list:
            if file['title'] == folder_name and file['mimeType'] == 'application/vnd.google-apps.folder':
                folder_exists = True
                folder_id = file['id']
                break

        if not folder_exists:
            folder_metadata = {
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive.CreateFile(folder_metadata)
            folder.Upload()
            folder_id = folder['id']
            print(f"Папка '{folder_path}' успешно создана на Google Drive.")

        return folder_id

    def upload_photo_to_google_drive(self, drive, file_name, folder_id):
        '''
        Данный метод загружает фотографию на Google Drive в необходимую папку.
        На вход подются данные об авторизации, название файла и папки.
        Возвращает информацию о результате резервного копирования фотографии.
        '''
        file_path = os.path.join(os.getcwd(), file_name)
        gfile = drive.CreateFile({"title": file_name, "parents": [{"id": folder_id}]})
        gfile.SetContentFile(file_path)
        gfile.Upload()
        print(f"Файл '{file_name}' успешно загружен на Google Drive.")

    def create_folder_on_yandex_disk(self, folder_path):
        '''
        Метод создает папку на Яндекс диск для хранения резервной копии фотографий.
        Если папка уже существует, выводится соответствующее сообщение.
        На вход подается необходимое название папки.
        Возвращается информация о результате создания папки.
        '''
        headers = {'Authorization': f"OAuth {self.yandex_token}"}
        url_create_folder = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {
            'path': folder_path
        }
        response = requests.put(url_create_folder, headers=headers, params=params)
        if response.status_code == 201:
            print(f'Папка "{folder_path}" успешно создана на Яндекс Диске.')
        elif response.status_code == 409:
            print(f'Папка "{folder_path}" уже существует на Яндекс Диске.')
        else:
            print('При создании папки на Яндекс Диске произошла ошибка')

    def upload_photo_yandex_disk(self, file_name, folder_path):
        '''
        Данный метод загружает фотографию на Яндекс диск в необходимую папку.
        На вход подется название файла и папки.
        Возвращает информацию о результате резервного копирования фотографии.
        '''
        headers = {'Authorization': f"OAuth {self.yandex_token}"}
        url_upload = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        params = {
            'path': f"{folder_path}/{file_name}",
            'overwrite': 'True'
        }
        response = requests.get(url_upload, headers=headers, params=params)
        data = response.json()
        href = data['href']
        with open(file_name, 'rb') as file:
            response = requests.put(href, files={'file': file})
        print(f'Фотография "{file_name}" успешно загружена на Яндекс Диск.')



if __name__ == '__main__':
    token = 'vk1.a.W6PxUtWXGpuyrIygZQRwJELAQa9tUS3s8i1E_xotvsBWP5wxANPq4FprmVuqrejh1Hr57stlReJYOj10UGrlQCfvgajV_inN4YNM_nVw2Zz5Ij7ZWsysaDb8yBS87RM5KWBQr8TcW-UBVs_x5pY-F_B1FNpt6BPI_kwm2Wrkq7Ktc5xYDZkXaFIQ3pZa1QkjO5VOsniO4_Q6iFQ49X6W4w'
    ya_token = '' # Введите токен Яндекс диска для резервного копирования
    user_id = input('Введите ID VK с которого необходимо сделать резервную копию: ')
    loader = VK(user_id, token, ya_token)
    result = loader.write()