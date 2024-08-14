from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.tab import MDTabs
from kivymd.uix.list import MDList, OneLineAvatarListItem, ImageLeftWidget
from googleapiclient.discovery import build
import requests
import isodate
import json
import os

YOUTUBE_API_KEY = 'AIzaSyCMYmuUsSoMwFv2G-mKm7-BA7-S-50NzR8'
SERVER_URL = 'http://127.0.0.1:5000/get_videos'
CACHE_FILE = 'assets/video_cache.json'

class SearchTab(BoxLayout, MDTabsBase):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = 'vertical'
        self.icon = 'magnify'
        self.title = 'Buscar Vídeos'

        self.search_input = TextInput(hint_text='Buscar vídeos no YouTube', size_hint_y=None, height=50)
        self.add_widget(self.search_input)

        self.search_button = Button(text='Buscar', size_hint_y=None, height=50)
        self.search_button.bind(on_press=self.search_videos)
        self.add_widget(self.search_button)

        self.search_results = MDList()
        self.search_scroll = ScrollView()
        self.search_scroll.add_widget(self.search_results)
        self.add_widget(self.search_scroll)

        self.search_input.bind(on_text_validate=self.search_videos)

    def search_videos(self, instance):
        query = self.search_input.text
        cache = self.load_cache()

        if query in cache and 'search' in cache[query]:
            print("Carregando resultados da busca do cache.")
            self.display_search_results(cache[query]['search'])
        else:
            print("Buscando vídeos na API do YouTube.")
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            try:
                request = youtube.search().list(
                    q=query,
                    part='snippet',
                    type='video',
                    maxResults=10
                )
                response = request.execute()
                if query not in cache:
                    cache[query] = {}
                cache[query]['search'] = response.get('items', [])
                self.save_cache(cache)
                self.display_search_results(response.get('items', []))
            except Exception as e:
                print(f"Erro ao buscar vídeos: {e}")

    def display_search_results(self, items):
        self.search_results.clear_widgets()
        for item in items:
            video_title = item['snippet']['title']
            video_id = item['id']['videoId']
            thumbnail_url = item['snippet']['thumbnails']['default']['url']

            list_item = OneLineAvatarListItem(text=video_title)
            image = ImageLeftWidget(source=thumbnail_url)
            list_item.add_widget(image)
            list_item.bind(on_press=lambda x, video_id=video_id: self.add_video_to_device(video_id))
            self.search_results.add_widget(list_item)

    def add_video_to_device(self, video_id):
        url = f'http://127.0.0.1:5000/add_video?video_id={video_id}'
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Vídeo adicionado com sucesso!")
                self.app.update_video_list()
            else:
                print(f"Erro ao adicionar vídeo: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão: {e}")

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    print("Cache carregado com sucesso.")
                    return cache
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erro ao carregar o cache: {e}")
                return {}
        return {}

    def save_cache(self, cache):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f)
                print("Cache salvo com sucesso.")
        except IOError as e:
            print(f"Erro ao salvar o cache: {e}")

class VideoListTab(BoxLayout, MDTabsBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.icon = 'playlist-play'
        self.title = 'Lista de Vídeos'

        self.video_list = MDList()
        self.list_scroll = ScrollView()
        self.list_scroll.add_widget(self.video_list)
        self.add_widget(self.list_scroll)

    def update_list(self, video_ids):
        cache = self.load_cache()
        uncached_video_ids = []

        if 'videos' in cache:
            uncached_video_ids = [video_id for video_id in video_ids if video_id not in cache['videos']]
        else:
            uncached_video_ids = video_ids

        if uncached_video_ids:
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            batch_size = 10

            for i in range(0, len(uncached_video_ids), batch_size):
                batch_ids = uncached_video_ids[i:i + batch_size]
                try:
                    request = youtube.videos().list(
                        part='snippet,contentDetails',
                        id=','.join(batch_ids)
                    )
                    response = request.execute()
                    if 'videos' not in cache:
                        cache['videos'] = {}
                    for item in response.get('items', []):
                        cache['videos'][item['id']] = item
                    self.save_cache(cache)
                    self.process_video_details(response.get('items', []))
                except Exception as e:
                    print(f"Erro ao buscar detalhes do vídeo: {e}")
        else:
            print("Carregando vídeos da lista do cache.")
            self.process_video_details([cache['videos'].get(video_id) for video_id in video_ids if video_id in cache['videos']])

    def process_video_details(self, video_items):
        self.video_list.clear_widgets()
        for item in video_items:
            try:
                video_title = item['snippet']['title']
                thumbnail_url = item['snippet']['thumbnails']['default']['url']
                duration = item['contentDetails']['duration']
                duration = self.format_duration(duration)

                list_item = OneLineAvatarListItem(text=f"{video_title} ({duration})")
                image = ImageLeftWidget(source=thumbnail_url)
                list_item.add_widget(image)
                self.video_list.add_widget(list_item)
            except Exception as e:
                print(f"Erro ao processar detalhes do vídeo: {e}")

    def format_duration(self, duration):
        duration = isodate.parse_duration(duration)
        minutes, seconds = divmod(int(duration.total_seconds()), 60)
        return f"{minutes}m {seconds}s"

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    print("Cache carregado com sucesso.")
                    return cache
            except (json.JSONDecodeError, IOError) as e:
                print(f"Erro ao carregar o cache: {e}")
                return {}
        return {}

    def save_cache(self, cache):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f)
                print("Cache salvo com sucesso.")
        except IOError as e:
            print(f"Erro ao salvar o cache: {e}")

class VideoApp(MDApp):
    def build(self):
        self.layout = BoxLayout(orientation='vertical')

        self.tabs = MDTabs()
        self.layout.add_widget(self.tabs)

        self.search_tab = SearchTab(app=self)
        self.list_tab = VideoListTab()

        self.tabs.add_widget(self.search_tab)
        self.tabs.add_widget(self.list_tab)

        Clock.schedule_interval(self.update_video_list, 30)

        return self.layout

    def update_video_list(self, *args):
        video_ids = self.get_video_list()
        self.list_tab.update_list(video_ids)

    def get_video_list(self):
        try:
            response = requests.get(SERVER_URL)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao carregar vídeos: {e}")
            return []

if __name__ == '__main__':
    VideoApp().run()
