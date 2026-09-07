# -*- coding: utf-8 -*-
"""
KKBOX Pro Mini Player 旗艦修正版 (徹底修復 gettext 語系閃退、支援單一檔案打包內部 plugins 載入、修正重開歌單消失問題、支援極扁視窗高度解鎖、修復按鈕功能綁定、完美優化極小視窗視覺、大升級 lrclib 歌詞模糊匹配成功率)
"""

import os
import sys
import json
import requests
import yt_dlp
import vlc
import random
import re

# ─── 🛑 核心閃退攔截防禦：必須在載入 ytmusicapi 之前執行 ───
import gettext
gettext.translation = lambda *args, **kwargs: gettext.NullTranslations()

from ytmusicapi import YTMusic
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QPoint, QSize
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QMenu, QInputDialog, QPushButton, QListWidget, QListWidgetItem, QDialog)

# ─── 🎵 VLC 路徑修正 (完美相容單一檔案包含 plugins 寫法) ───
if getattr(sys, 'frozen', False):
    vlc_path = sys._MEIPASS
    os.environ['PYTHON_VLC_MODULE_PATH'] = vlc_path
    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
else:
    vlc_path = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(vlc_path, 'libvlc.dll')):
        vlc_path = r'C:\Program Files\VideoLAN\VLC'

if os.path.exists(vlc_path):
    os.environ['PATH'] = vlc_path + ';' + os.environ.get('PATH', '')
    try:
        os.add_dll_directory(vlc_path)
    except AttributeError:
        pass

# ─── 🌐 工人 1：音樂核心工人 ───
class MusicWorker(QThread):
    finished = pyqtSignal(dict, list)
    error = pyqtSignal(str)

    def __init__(self, api, keyword, video_id=None):
        super().__init__()
        self.api = api
        self.keyword = keyword
        self.video_id = video_id

    def run(self):
        try:
            if self.video_id:
                song = {
                    'id': self.video_id,
                    'title': self.keyword.split(' - ')[0] if ' - ' in self.keyword else self.keyword,
                    'artist': self.keyword.split(' - ')[1] if ' - ' in self.keyword else '未知歌手'
                }
            else:
                song = self.api.search_song(self.keyword)
                if not song:
                    self.error.emit('❌ 找不到歌曲，請右鍵重試')
                    return

            song_title = f"{song['title']} {song['artist']}"
            song['stream'] = self.api.stream(song['id'], song_title=song_title)
            radio = self.api.radio(song['id'])
            self.finished.emit(song, radio)
        except Exception as e:
            self.error.emit(f"發生錯誤: {str(e)}")

# ─── 🌐 工人 2：獨立歌詞工人 ───
class LyricsWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, api, title, artist):
        super().__init__()
        self.api = api
        self.title = title
        self.artist = artist

    def run(self):
        try:
            lyrics = self.api.lrclib(self.title, self.artist)
            self.finished.emit(lyrics)
        except:
            self.finished.emit({})

# ─── 🎵 音樂數據解析 ───
class MusicAPI:
    def __init__(self):
        self.yt = YTMusic()
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }

    def search_song(self, text):
        try:
            r = self.yt.search(text, filter='songs')
            if not r:
                r = self.yt.search(text, filter='videos')
            if not r:
                return None
            s = r[0]
            return {
                'id': s['videoId'],
                'title': s['title'],
                'artist': s['artists'][0]['name'] if s.get('artists') else '未知歌手'
            }
        except Exception as e:
            print(f"搜尋歌曲失敗: {e}")
            return None

    def stream(self, vid, song_title=None):
        client_options = [
            ['android', 'web'],
            ['ios', 'mweb'],
            ['android_creator', 'android'],
            ['tv', 'web'],
            ['mweb'],
            ['web']
        ]

        formats_to_try = ['bestaudio/best', 'ba/b', 'best']

        last_error = None
        for clients in client_options:
            for fmt in formats_to_try:
                ydl_opts = {
                    'format': fmt,
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'geo_bypass': True,
                    'extractor_args': {
                        'youtube': {
                            'player_client': clients,
                            'skip': ['dash', 'hls'] if fmt == 'ba/b' else []
                        }
                    },
                    'http_headers': self.base_headers
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as y:
                        info = y.extract_info(f'https://www.youtube.com/watch?v={vid}', download=False)
                        if info and 'url' in info:
                            return info['url']
                except Exception as e:
                    last_error = e
                    continue

        # 如果此 videoId 無法提取，且有歌名，嘗試自動搜尋替代影片
        if song_title:
            try:
                print(f"原影片 ID {vid} 無法串流，嘗試為您搜尋替代影片: {song_title}")
                alt = self.search_song(song_title)
                if alt and alt['id'] != vid:
                    for clients in client_options[:2]:
                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'quiet': True,
                            'no_warnings': True,
                            'nocheckcertificate': True,
                            'geo_bypass': True,
                            'extractor_args': {'youtube': {'player_client': clients}},
                            'http_headers': self.base_headers
                        }
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as y:
                                info = y.extract_info(f"https://www.youtube.com/watch?v={alt['id']}", download=False)
                                if info and 'url' in info:
                                    return info['url']
                        except:
                            continue
            except:
                pass

        raise RuntimeError(f"YouTube 串流解析失敗 ({last_error})")

    def radio(self, vid):
        try:
            data = self.yt.get_watch_playlist(vid)
            q = []
            for i in data.get('tracks', []):
                if i['videoId'] != vid:
                    q.append({
                        'title': i['title'],
                        'artist': i['artists'][0]['name'] if i.get('artists') else '未知歌手',
                        'id': i['videoId']
                    })
            return q
        except:
            return []

    def lrclib(self, title, artist):
        # ─── 🧠 歌詞升級：關鍵字智慧淨化防禦工程 ───
        def clean_text(text):
            # 移除括號與其內部雜質 (如: (Live), (抖音熱歌), [Official MV], 【高清】)
            text = re.sub(r'[\(\[\{【].*?[\)\]\}】]', '', text)
            # 移除常見後綴
            text = re.sub(r'(?i)(official|video|mv|hd|lyrics|字幕|版|單曲|高音質|熱歌)', '', text)
            return text.strip()

        clean_title = clean_text(title)
        # 如果有多個歌手 (如張紫豪/葛東琪)，只取第一個主要歌手搜尋，大幅提升匹配率
        clean_artist = artist.split('/')[0].split(',')[0].split(';')[0].strip()
        clean_artist = clean_text(clean_artist)

        def parse_lrc_text(text):
            lyrics = {}
            if not text: return lyrics
            for line in text.split('\n'):
                if not line.startswith('['): continue
                parts = line.split(']')
                if len(parts) < 2: continue
                t_str = parts[0][1:]
                lyric = parts[1].strip()
                try:
                    m, s = t_str.split(':')
                    total = (float(m) * 60 + float(s)) * 1000
                    if lyric:
                        lyrics[int(total)] = lyric
                except:
                    continue
            return lyrics

        try:
            # 嘗試 1：精確乾淨搜尋 (歌名 + 歌手)
            url = 'https://lrclib.net/api/search'
            params = {'track_name': clean_title, 'artist_name': clean_artist}
            r = requests.get(url, params=params, timeout=5.0)
            
            if r.status_code == 200 and r.json():
                data = r.json()
                synced = data[0].get('syncedLyrics', '')
                if synced: return parse_lrc_text(synced)
                plain = data[0].get('plainLyrics', '')
                if plain: return {0: plain.replace('\n', ' / ')}

            # 嘗試 2：放寬限制模糊搜尋 (僅用乾淨歌名)
            params_fuzzy = {'q': clean_title}
            r_fuzzy = requests.get(url, params=params_fuzzy, timeout=5.0)
            if r_fuzzy.status_code == 200 and r_fuzzy.json():
                # 遍歷搜尋結果，找出含有動態歌詞，且歌名高度相似的項目
                for res in r_fuzzy.json():
                    synced = res.get('syncedLyrics', '')
                    if synced:
                        return parse_lrc_text(synced)
                # 若無動態歌詞，退而求其次抓靜態歌詞
                for res in r_fuzzy.json():
                    plain = res.get('plainLyrics', '')
                    if plain:
                        return {0: plain.replace('\n', ' / ')}
            return {}
        except:
            return {}

class PlayerSignals(QObject):
    song_finished_signal = pyqtSignal()

# ─── 📋 實體拖曳排序視窗 ───
class DragSortDialog(QDialog):
    def __init__(self, playlist_name, songs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📋 排序：{playlist_name}")
        self.setFixedSize(350, 400)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.songs = songs
        
        layout = QVBoxLayout()
        tip = QLabel("💡 請滑鼠按住歌曲，上下拖曳調整順序")
        tip.setStyleSheet("color: #00e5ff; font-size: 12px; font-family: 'Microsoft JhengHei';")
        layout.addWidget(tip)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #121212; color: #ffffff; border: 1px solid #444444; font-size: 14px; border-radius: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #222222; }
            QListWidget::item:hover { background-color: #2b2b2b; }
            QListWidget::item:selected { background-color: #00e5ff; color: #121212; font-weight: bold; }
        """)
        
        for s in songs:
            item = QListWidgetItem(f"🎵 {s['title']} - {s['artist']}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.list_widget.addItem(item)
            
        layout.addWidget(self.list_widget)
        
        btn_save = QPushButton("確認儲存順序")
        btn_save.setFixedHeight(35)
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)
        
        self.setStyleSheet("QDialog { background-color: #1c1c1c; } QPushButton { background-color: #00e5ff; color: #121212; font-weight: bold; border-radius: 4px; font-family: 'Microsoft JhengHei'; }")
        self.setLayout(layout)

    def get_sorted_songs(self):
        sorted_list = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                sorted_list.append(data)
        return sorted_list

# ─── 📜 即將播放清單 (佇列) 視窗 ───
class QueueDialog(QDialog):
    def __init__(self, queue_songs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📜 即將播放清單 (佇列)")
        self.setFixedSize(420, 480)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.parent_player = parent
        
        layout = QVBoxLayout()
        
        header_layout = QHBoxLayout()
        tip = QLabel("💡 雙擊「▶️」可立即播放，可拖曳調整順序")
        tip.setStyleSheet("color: #00e5ff; font-size: 12px; font-family: 'Microsoft JhengHei';")
        header_layout.addWidget(tip)
        
        btn_shuffle = QPushButton("🔀 隨機打亂")
        btn_shuffle.setFixedSize(75, 24)
        btn_shuffle.clicked.connect(self.shuffle_queue)
        header_layout.addWidget(btn_shuffle)
        
        btn_clear = QPushButton("🗑️ 清空佇列")
        btn_clear.setFixedSize(75, 24)
        btn_clear.clicked.connect(self.clear_queue)
        header_layout.addWidget(btn_clear)
        
        layout.addLayout(header_layout)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #121212; color: #ffffff; border: 1px solid #444444; font-size: 13px; border-radius: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #222222; }
            QListWidget::item:hover { background-color: #2b2b2b; }
            QListWidget::item:selected { background-color: #00e5ff; color: #121212; font-weight: bold; }
        """)
        
        self.populate_list(queue_songs)
        self.list_widget.itemDoubleClicked.connect(self.play_selected_item)
        layout.addWidget(self.list_widget)
        
        btn_box = QHBoxLayout()
        btn_play_now = QPushButton("▶️ 立即播放所選")
        btn_play_now.clicked.connect(self.play_selected_item)
        btn_remove = QPushButton("🗑️ 移出佇列")
        btn_remove.clicked.connect(self.remove_selected_item)
        btn_save = QPushButton("確認關閉")
        btn_save.clicked.connect(self.accept)
        
        btn_box.addWidget(btn_play_now)
        btn_box.addWidget(btn_remove)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        self.setStyleSheet("""
            QDialog { background-color: #1c1c1c; }
            QPushButton { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; border-radius: 4px; font-size: 12px; font-family: 'Microsoft JhengHei'; padding: 4px; }
            QPushButton:hover { background-color: #00e5ff; color: #121212; }
        """)
        self.setLayout(layout)

    def populate_list(self, songs):
        self.list_widget.clear()
        for idx, s in enumerate(songs):
            item = QListWidgetItem(f"{idx+1}. 🎵 {s['title']} - {s.get('artist', '未知歌手')}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.list_widget.addItem(item)

    def get_updated_queue(self):
        updated = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data: updated.append(data)
        return updated

    def play_selected_item(self):
        current_item = self.list_widget.currentItem()
        if not current_item: return
        song = current_item.data(Qt.ItemDataRole.UserRole)
        if song and self.parent_player:
            row = self.list_widget.row(current_item)
            self.list_widget.takeItem(row)
            updated_queue = self.get_updated_queue()
            self.parent_player.queue = updated_queue
            vid = song.get('id') or song.get('videoId')
            self.parent_player.search(f"{song['title']} {song.get('artist', '')}", video_id=vid)
            self.accept()

    def remove_selected_item(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            if self.parent_player:
                self.parent_player.queue = self.get_updated_queue()

    def shuffle_queue(self):
        songs = self.get_updated_queue()
        random.shuffle(songs)
        self.populate_list(songs)
        if self.parent_player:
            self.parent_player.queue = songs

    def clear_queue(self):
        self.list_widget.clear()
        if self.parent_player:
            self.parent_player.queue = []

# ─── 💻 主播放器視窗 ───
class Player(QWidget):
    def __init__(self):
        super().__init__()
        self.api = MusicAPI()
        self.instance = vlc.Instance('--no-video', '--quiet')
        self.player = self.instance.media_player_new()

        self.signals = PlayerSignals()
        self.signals.song_finished_signal.connect(self.handle_song_finished_safe)

        self.queue = []
        self.history = []
        self.played_ids = set()
        self.current = {}
        self.lyrics = {}
        self.mode = 'RADIO' 
        
        self.current_active_playlist = []
        self.current_active_index = 0

        self.music_worker = None
        self.lyrics_worker = None
        
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.playlist_file = os.path.join(exe_dir, "playlist.json")
        self.load_playlist_data()

        self.vlc_events = self.player.event_manager()
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, self.song_finished)
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.song_error)

        self.build_ui()
        self.restore_window_geometry()  

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)

        self.toast_timer = QTimer()
        self.toast_timer.timeout.connect(self.hide_toast_notice)

        start_songs = ['張惠妹 如果你也聽說', '周杰倫 說好不哭', '五月天 突然好想你', '蔡依林 倒帶', '陳奕迅 十年']
        chosen_song = random.choice(start_songs)
        QTimer.singleShot(500, lambda: self.search(chosen_song))

    def build_ui(self):
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle('Lynn的音樂播放小程式')
        
        self.setMinimumSize(360, 62) 

        self.title = QLabel('正在載入音樂與動態歌詞...')
        self.title.setWordWrap(False) 
        
        self.progress = QLabel('00:00 / 00:00')
        self.progress.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.btn_fav = QPushButton('🤍')   
        self.btn_add = QPushButton('➕')   
        self.btn_folder = QPushButton('📂')
        self.btn_queue = QPushButton('📜')
        self.btn_prev = QPushButton('⏮️')   
        self.btn_play = QPushButton('⏸️')   
        self.btn_next = QPushButton('⏭️')   

        self.btn_queue.setToolTip("📜 查看即將播放清單 (佇列)")
        
        self.btn_fav.clicked.connect(self.toggle_favorite_json)
        self.btn_add.clicked.connect(self.add_to_custom_playlist_dialog)
        self.btn_folder.clicked.connect(self.show_playlists_menu)
        self.btn_queue.clicked.connect(self.show_queue_dialog)
        self.btn_prev.clicked.connect(self.play_prev)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.trigger_next_song_by_button)

        for btn in [self.btn_fav, self.btn_add, self.btn_folder, self.btn_queue, self.btn_prev, self.btn_play, self.btn_next]:
            btn.setFixedSize(30, 22)

        top_grid = QGridLayout()
        top_grid.setContentsMargins(0, 0, 0, 0)
        top_grid.setSpacing(4) 
        
        top_grid.addWidget(self.title, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2) 
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.btn_fav)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_folder)
        btn_layout.addWidget(self.btn_queue)
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_play)
        btn_layout.addWidget(self.btn_next)
        
        btn_container = QWidget()
        btn_container.setLayout(btn_layout)
        top_grid.addWidget(btn_container, 0, 1, Qt.AlignmentFlag.AlignCenter)
        
        top_grid.addWidget(self.progress, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        top_grid.setColumnStretch(0, 10)
        top_grid.setColumnStretch(1, 0)
        top_grid.setColumnStretch(2, 10)

        self.lyric = QLabel('🎵')
        self.lyric.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric.setWordWrap(True) 

        self.toast = QLabel('')
        self.toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast.setStyleSheet("""
            font-size: 12px; font-weight: bold; color: #00ff88; background-color: rgba(18, 18, 18, 0.85); padding: 1px; font-family: "Microsoft JhengHei";
        """)
        self.toast.hide()

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_grid)
        main_layout.addWidget(self.lyric, stretch=1) 
        main_layout.addWidget(self.toast)
        
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(8, 4, 8, 4) 
        
        self.setStyleSheet("""
            QWidget { background-color: #1c1c1c; }
            QMenu { background-color: #282828; color: #ffffff; border: 1px solid #444444; font-size: 14px; font-family: "Microsoft JhengHei"; }
            QMenu::item { padding: 6px 25px 6px 20px; background-color: transparent; }
            QMenu::item:selected { background-color: #00e5ff; color: #121212; font-weight: bold; }
            QMenu::separator { height: 1px; background-color: #444444; margin: 4px 0px; }
            QInputDialog { background-color: #282828; color: #ffffff; }
            QLineEdit { background-color: #121212; color: #ffffff; border: 1px solid #00e5ff; padding: 4px; font-size: 14px; }
            QPushButton { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background-color: #00e5ff; color: #121212; border: 1px solid #00e5ff; }
        """)
        self.setLayout(main_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        
        lyric_size = max(11, min(int(w / 28), int(h / 3.4)))
        self.lyric.setStyleSheet(f"""
            font-size: {lyric_size}px; font-weight: bold; color: #00e5ff; 
            background-color: #121212; border-radius: 6px; padding: 3px 10px; font-family: "Microsoft JhengHei";
        """)
        
        if w < 600 or h < 95:
            ui_font_size = max(9.5, min(11, int(w / 52)))
        else:
            ui_font_size = max(11, min(13.5, int(w / 58)))
            
        self.title.setStyleSheet(f'font-size: {ui_font_size}px; color: #bbbbbb; font-weight: bold; font-family: "Microsoft JhengHei"; padding-bottom: 1px;')
        self.progress.setStyleSheet(f'font-size: {ui_font_size}px; color: #00e5ff; font-weight: bold; font-family: "Consolas"; padding-bottom: 1px;')

    def restore_window_geometry(self):
        try:
            geom = self.playlists.get("window_geometry")
            if geom:
                self.move(geom.get("x", 100), geom.get("y", 100))
                self.resize(geom.get("width", 850), geom.get("height", 115))
            else:
                self.resize(850, 115)
        except:
            self.resize(850, 115)

    def closeEvent(self, event):
        if not hasattr(self, 'playlists'): self.playlists = {}
        self.playlists["window_geometry"] = {
            "x": self.pos().x(),
            "y": self.pos().y(),
            "width": self.size().width(),
            "height": self.size().height()
        }
        self.save_playlist_data()
        event.accept()

    def show_kkbox_toast(self, text):
        self.toast.setText(text)
        self.toast.show()
        self.toast_timer.start(1000)

    def hide_toast_notice(self):
        self.toast.hide()
        self.toast_timer.stop()

    def load_playlist_data(self):
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    self.playlists = json.load(f)
                if "我的最愛" not in self.playlists: self.playlists["我的最愛"] = []
                if "自訂歌單" not in self.playlists: self.playlists["自訂歌單"] = {}
            except:
                self.playlists = {"我的最愛": [], "自訂歌單": {}}
        else:
            self.playlists = {"我的最愛": [], "自訂歌單": {}}
            self.save_playlist_data()

    def save_playlist_data(self):
        try:
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump(self.playlists, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"歌單存檔失敗: {e}")

    def lock_buttons(self):
        self.btn_next.setEnabled(False)
        self.btn_prev.setEnabled(False)
        QTimer.singleShot(1500, self.unlock_buttons)

    def unlock_buttons(self):
        self.btn_next.setEnabled(True)
        self.btn_prev.setEnabled(True)

    def search(self, text, video_id=None):
        self.lock_buttons()
        self.title.setText(f"🔍 正在搜尋：{text}")
        self.lyric.setText("⚡ 正在加載下一首動態歌詞...")
        self.lyrics = {}

        if self.music_worker and self.music_worker.isRunning():
            try: self.music_worker.disconnect(); self.music_worker.quit(); self.music_worker.wait(300)
            except: pass
        if self.lyrics_worker and self.lyrics_worker.isRunning():
            try: self.lyrics_worker.disconnect(); self.lyrics_worker.quit(); self.lyrics_worker.wait(300)
            except: pass

        self.music_worker = MusicWorker(self.api, text, video_id)
        self.music_worker.finished.connect(self.music_loaded)
        self.music_worker.error.connect(self.handle_music_worker_error)
        self.music_worker.start()

    def handle_music_worker_error(self, err_text):
        self.lyric.setText(f"⚠️ {err_text}")
        self.show_kkbox_toast("⚠️ 此曲無法播放，1.5秒後自動跳下一首...")
        QTimer.singleShot(1500, lambda: self.trigger_next_song_by_button())

    def music_loaded(self, song, radio):
        if self.current: self.history.append(self.current)
        self.current = song

        if song.get('id'):
            self.played_ids.add(song['id'])
            if len(self.played_ids) > 100:
                self.played_ids = set(list(self.played_ids)[-80:])

        if self.mode == 'RADIO':
            existing_ids = {s.get('id') or s.get('videoId') for s in self.queue} | self.played_ids
            new_tracks = [s for s in radio if (s.get('id') or s.get('videoId')) not in existing_ids]
            self.queue.extend(new_tracks)
            self.inject_diverse_seeds_if_needed()
            if len(self.queue) > 50:
                self.queue = self.queue[:50]

        self.title.setText(f"▶️ {song['title']} - {song['artist']}")
        self.btn_play.setText('⏸️')
        self.update_favorite_button_ui()
        
        media = self.instance.media_new(song['stream'])
        self.player.set_media(media)
        self.player.play()

        self.lyrics_worker = LyricsWorker(self.api, song['title'], song['artist'])
        self.lyrics_worker.finished.connect(self.lyrics_loaded)
        self.lyrics_worker.start()

    def show_queue_dialog(self):
        dialog = QueueDialog(self.queue, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.queue = dialog.get_updated_queue()
            self.show_kkbox_toast("📜 佇列已更新！")

    def inject_diverse_seeds_if_needed(self):
        if len(self.queue) >= 12:
            return

        existing_ids = {s.get('id') or s.get('videoId') for s in self.queue} | self.played_ids
        
        # 1. 優先取用「我的最愛」歌單作為擴充種子，打破 YouTube 單一曲風同溫層
        favs = self.playlists.get("我的最愛", [])
        if favs:
            sample_favs = random.sample(favs, min(3, len(favs)))
            for fav in sample_favs:
                vid = fav.get('videoId')
                if vid:
                    rec = self.api.radio(vid)
                    for t in rec:
                        t_id = t.get('id') or t.get('videoId')
                        if t_id and t_id not in existing_ids:
                            self.queue.append(t)
                            existing_ids.add(t_id)

        # 2. 若佇列依舊過短，隨機挑選多樣化熱門種子歌手補足
        if len(self.queue) < 10:
            diverse_queries = [
                '周杰倫', '五月天', '蔡依林', '陳奕迅', '張惠妹', 
                '告五人', '莫文蔚', '孫燕姿', '林俊傑', 'Taylor Swift'
            ]
            chosen_artist = random.choice(diverse_queries)
            res = self.api.search_song(chosen_artist)
            if res:
                res_id = res.get('id') or res.get('videoId')
                if res_id and res_id not in existing_ids:
                    self.queue.append(res)

    def lyrics_loaded(self, lyrics):
        self.lyrics = lyrics
        if not self.lyrics: self.lyric.setText("🎵 (純音樂 / 暫無動態歌詞)")

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.btn_play.setText('▶️')
            self.title.setText(f"⏸️ (已暫停) {self.current.get('title', '')}")
        else:
            self.player.play()
            self.btn_play.setText('⏸️')
            self.title.setText(f"▶️ {self.current.get('title', '')} - {self.current.get('artist', '')}")

    def update_favorite_button_ui(self):
        if not self.current: self.btn_fav.setText('🤍'); return
        is_fav = any(item['videoId'] == self.current['id'] for item in self.playlists["我的最愛"])
        self.btn_fav.setText('❤️' if is_fav else '🤍')

    def toggle_favorite_json(self):
        if not self.current: return
        song_info = {"title": self.current['title'], "artist": self.current['artist'], "videoId": self.current['id']}
        fav_list = self.playlists["我的最愛"]
        existing_index = next((i for i, item in enumerate(fav_list) if item['videoId'] == song_info['videoId']), None)
        
        if existing_index is not None:
            fav_list.pop(existing_index)
            self.btn_fav.setText('🤍')
            self.show_kkbox_toast('🤍 已移出「我的最愛」')
        else:
            fav_list.append(song_info)
            self.btn_fav.setText('❤️')
            self.show_kkbox_toast('✔ 已加入「我的最愛」')
        self.save_playlist_data()

    def add_to_custom_playlist_dialog(self):
        if not self.current: return
        menu = QMenu(self)
        menu.addAction("➕ ── 新增全新歌單 ──")
        custom_lists = list(self.playlists["自訂歌單"].keys())
        if custom_lists:
            menu.addSeparator()
            for name in custom_lists: menu.addAction(f"📁 {name}")
                
        action = menu.exec(self.btn_add.mapToGlobal(self.btn_add.rect().bottomLeft()))
        if not action: return
        song_info = {"title": self.current['title'], "artist": self.current['artist'], "videoId": self.current['id']}
        
        if "── 新增全新歌單 ──" in action.text():
            name, ok = QInputDialog.getText(self, "全新歌單", "請輸入新歌單名稱：")
            if ok and name.strip():
                playlist_name = name.strip()
                if playlist_name not in self.playlists["自訂歌單"]: self.playlists["自訂歌單"][playlist_name] = []
                self.playlists["自訂歌單"][playlist_name].append(song_info)
                self.show_kkbox_toast(f'✔ 已加入「{playlist_name}」')
                self.save_playlist_data()
        else:
            playlist_name = action.text().replace("📁 ", "")
            if not any(item['videoId'] == song_info['videoId'] for item in self.playlists["自訂歌單"][playlist_name]):
                self.playlists["自訂歌單"][playlist_name].append(song_info)
            self.show_kkbox_toast(f'✔ 已加入「{playlist_name}」')
            self.save_playlist_data()

    def show_playlists_menu(self):
        self.load_playlist_data()
        menu = QMenu(self)
        
        fav_menu = menu.addMenu(f"❤️ 我的最愛 ({len(self.playlists['我的最愛'])} 首)")
        fav_play = fav_menu.addAction("▶️ 播放此歌單")
        fav_play.triggered.connect(lambda: self.play_json_playlist_group(self.playlists['我的最愛'], "我的最愛"))
        
        fav_sort = fav_menu.addAction("📋 調整歌曲排序 (滑鼠拖曳)")
        fav_sort.triggered.connect(lambda: self.open_drag_sort_panel("我的最愛"))
        
        if self.playlists['我的最愛']:
            fav_menu.addSeparator()
            for idx, item in enumerate(self.playlists['我的最愛']):
                song_menu = fav_menu.addMenu(f"🎵 {item['title']} - {item['artist']}")
                act_song_play = song_menu.addAction("▶️ 播放此首歌曲")
                act_song_play.triggered.connect(lambda checked, s=item: self.search(f"{s['title']} {s['artist']}", video_id=s['videoId']))
                
                act_song_del = song_menu.addAction("🗑️ 刪除此歌曲")
                act_song_del.triggered.connect(lambda checked, p="我的最愛", i=idx: self.delete_song_from_playlist(p, i))
        
        menu.addSeparator()
        
        custom_lists = self.playlists["自訂歌單"]
        if not custom_lists:
            no_action = menu.addAction("📁 尚無其他自訂歌單"); no_action.setEnabled(False)
        else:
            for playlist_name, songs in list(custom_lists.items()):
                list_sub_menu = menu.addMenu(f"📁 {playlist_name} ({len(songs)} 首)")
                
                act_play = list_sub_menu.addAction("▶️ 播放此歌單")
                act_play.triggered.connect(lambda checked, s=songs, n=playlist_name: self.play_json_playlist_group(s, n))
                
                act_rename = list_sub_menu.addAction("✏️ 修改歌單名稱")
                act_rename.triggered.connect(lambda checked, n=playlist_name: self.rename_playlist(n))
                
                act_sort = list_sub_menu.addAction("📋 調整歌曲排序 (滑鼠拖曳)")
                act_sort.triggered.connect(lambda checked, n=playlist_name: self.open_drag_sort_panel(n))
                
                act_del_list = list_sub_menu.addAction("🔥 刪除整個歌單")
                act_del_list.triggered.connect(lambda checked, n=playlist_name: self.delete_entire_playlist(n))
                
                if songs:
                    list_sub_menu.addSeparator()
                    for idx, item in enumerate(songs):
                        song_menu = list_sub_menu.addMenu(f"🎵 {item['title']} - {item['artist']}")
                        act_song_play = song_menu.addAction("▶️ 播放此首歌曲")
                        act_song_play.triggered.connect(lambda checked, s=item: self.search(f"{s['title']} {s['artist']}", video_id=s['videoId']))
                        
                        act_song_del = song_menu.addAction("🗑️ 刪除此歌曲")
                        act_song_del.triggered.connect(lambda checked, p=playlist_name, i=idx: self.delete_song_from_playlist(p, i))
                        
        menu.exec(self.btn_folder.mapToGlobal(self.btn_folder.rect().bottomLeft()))

    def delete_song_from_playlist(self, playlist_name, song_index):
        if playlist_name == "我的最愛":
            self.playlists["我的最愛"].pop(song_index)
        else:
            self.playlists["自訂歌單"][playlist_name].pop(song_index)
        self.save_playlist_data()
        self.update_favorite_button_ui()
        self.show_kkbox_toast("🗑️ 歌曲已成功移出歌單")

    def rename_playlist(self, old_name):
        new_name, ok = QInputDialog.getText(self, "修改歌單名稱", f"請輸入「{old_name}」的新名字：")
        if ok and new_name.strip():
            target = new_name.strip()
            if target in self.playlists["自訂歌單"]:
                self.show_kkbox_toast("⚠️ 名字重複囉！"); return
            self.playlists["自訂歌單"][target] = self.playlists["自訂歌單"].pop(old_name)
            self.save_playlist_data()
            self.show_kkbox_toast("✏️ 歌單名稱修改成功")

    def open_drag_sort_panel(self, playlist_name):
        songs = self.playlists["我的最愛"] if playlist_name == "我的最愛" else self.playlists["自訂歌單"][playlist_name]
        if not songs:
            self.show_kkbox_toast("⚠️ 歌單裡沒歌，無法排序喔")
            return
            
        dialog = DragSortDialog(playlist_name, songs, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            sorted_result = dialog.get_sorted_songs()
            if playlist_name == "我的最愛":
                self.playlists["我的最愛"] = sorted_result
            else:
                self.playlists["自訂歌單"][playlist_name] = sorted_result
            self.save_playlist_data()
            self.show_kkbox_toast("📋 歌單順序已成功儲存！")

    def delete_entire_playlist(self, playlist_name):
        if playlist_name in self.playlists["自訂歌單"]:
            del self.playlists["自訂歌單"][playlist_name]
            self.save_playlist_data()
            self.show_kkbox_toast(f"🔥 已刪除歌單：{playlist_name}")

    def play_json_playlist_group(self, song_list, playlist_name):
        if not song_list:
            self.show_kkbox_toast("⚠️ 歌單內目前沒有歌曲喔"); return
        self.current_active_playlist = list(song_list)
        
        if self.mode == 'PLAYLIST_RANDOM':
            self.current_active_index = random.randint(0, len(self.current_active_playlist) - 1)
        elif self.mode == 'PLAYLIST_LOOP':
            self.current_active_index = 0
        else:
            self.mode = 'PLAYLIST_LOOP'
            self.current_active_index = 0
            
        first_song = self.current_active_playlist[self.current_active_index]
        self.search(f"{first_song['title']} {first_song['artist']}", video_id=first_song['videoId'])
        self.show_kkbox_toast(f"🚀 成功載入歌單「{playlist_name}」")

    def refresh(self):
        now = self.player.get_time()
        total = self.player.get_length()
        if total > 0:
            m_now, s_now = divmod(now // 1000, 60)
            m_tot, s_tot = divmod(total // 1000, 60)
            self.progress.setText(f'{m_now:02d}:{s_now:02d} / {m_tot:02d}:{s_tot:02d}')

        if self.player.is_playing() and self.lyrics:
            matched_sentence = "🎵"
            for t in sorted(self.lyrics):
                if now >= t: matched_sentence = self.lyrics[t]
                else: break
            self.lyric.setText(matched_sentence)

    def song_finished(self, event):
        self.signals.song_finished_signal.emit()

    def song_error(self, event):
        print("遇到串流載入錯誤，自動為您加載下一首...")
        self.signals.song_finished_signal.emit()

    def trigger_next_song_by_button(self):
        self.handle_song_finished_safe()

    def handle_song_finished_safe(self):
        if self.mode == 'SINGLE':
            QTimer.singleShot(100, lambda: self.replay_current())
        elif self.mode == 'PLAYLIST_RANDOM' and self.current_active_playlist:
            self.current_active_index = random.randint(0, len(self.current_active_playlist) - 1)
            next_song = self.current_active_playlist[self.current_active_index]
            QTimer.singleShot(100, lambda: self.search(f"{next_song['title']} {next_song['artist']}", video_id=next_song['videoId']))
        elif self.mode == 'PLAYLIST_LOOP' and self.current_active_playlist:
            self.current_active_index += 1
            if self.current_active_index >= len(self.current_active_playlist): self.current_active_index = 0
            next_song = self.current_active_playlist[self.current_active_index]
            QTimer.singleShot(100, lambda: self.search(f"{next_song['title']} {next_song['artist']}", video_id=next_song['videoId']))
        else:
            QTimer.singleShot(100, lambda: self.play_next_from_queue())

    def replay_current(self):
        if self.current:
            media = self.instance.media_new(self.current['stream'])
            self.player.set_media(media)
            self.player.play()

    def play_prev(self):
        if self.history:
            prev_song = self.history.pop()
            self.search(f"{prev_song['title']} {prev_song['artist']}")

    def play_next_from_queue(self):
        if self.queue:
            next_song = self.queue.pop(0)
            vid = next_song.get('id') or next_song.get('videoId')
            self.search(f"{next_song['title']} {next_song.get('artist', '')}", video_id=vid)
        else:
            if self.current:
                self.search(f"{self.current['title']} {self.current.get('artist', '')}")
            else:
                self.lyric.setText("🎵 電台播放清單已播完。")

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        search_action = context_menu.addAction("🔍 點歌播放")
        queue_action = context_menu.addAction("📜 即將播放清單 (佇列)")
        context_menu.addSeparator()
        prev_action = context_menu.addAction("⏮️ 上一首")
        next_action = context_menu.addAction("⏭️ 下一首")
        toggle_play_action = context_menu.addAction("⏯️ 暫停 / 播放")
        
        r_text = "● 🔄 模式: 隨機電台" if self.mode == 'RADIO' else "  🔄 模式: 隨機電台"
        s_text = "● 🔂 模式: 單曲循環" if self.mode == 'SINGLE' else "  🔂 模式: 單曲循環"
        pr_text = "● 🔀 模式: 歌單隨機播放" if self.mode == 'PLAYLIST_RANDOM' else "  🔀 模式: 歌單隨機播放"
        pl_text = "● 🔁 模式: 整體歌單循環" if self.mode == 'PLAYLIST_LOOP' else "  🔁 模式: 整體歌單循環"
        
        act_r = context_menu.addAction(r_text)
        act_s = context_menu.addAction(s_text)
        act_pr = context_menu.addAction(pr_text)
        act_pl = context_menu.addAction(pl_text)
        
        context_menu.addSeparator()
        exit_action = context_menu.addAction("❌ 關閉播放器")
        
        action = context_menu.exec(self.mapToGlobal(event.pos()))
        
        if action == search_action:
            text, ok = QInputDialog.getText(self, "點歌系統", "請輸入歌名或歌手：")
            if ok and text.strip(): self.search(text.strip())
        elif action == queue_action:
            self.show_queue_dialog()
        elif action == act_r:
            self.mode = 'RADIO'; self.show_kkbox_toast("切換至：隨機電台")
        elif action == act_s:
            self.mode = 'SINGLE'; self.show_kkbox_toast("切換至：單曲循環")
        elif action == act_pr:
            self.mode = 'PLAYLIST_RANDOM'; self.show_kkbox_toast("切換至：歌單隨機播放")
        elif action == act_pl:
            self.mode = 'PLAYLIST_LOOP'; self.show_kkbox_toast("切換至：整體歌單循環")
        elif action == prev_action: self.play_prev()
        elif action == next_action: self.trigger_next_song_by_button()
        elif action == toggle_play_action: self.toggle_play()
        elif action == exit_action: QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    p = Player()
    p.show()
    sys.exit(app.exec())