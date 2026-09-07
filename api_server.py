# -*- coding: utf-8 -*-
"""
Lynn-music Mobile API & Web Server
專為手機版設計的輕量級伺服器 (零額外依賴，內建多執行緒 HTTP 伺服器)
提供手機 PWA 靜態網頁託管與後端音樂解析 API
"""

import os
import sys
import json
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# 匯入核心音樂解析引擎
from music_core import MusicAPI

api_engine = MusicAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')

class LynnRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        # 允許跨域請求 (CORS) 與關閉暫存
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # ─── 🌐 API 路由分流 ───
        if path == '/api/search':
            self.handle_search(query)
        elif path == '/api/stream':
            self.handle_stream(query)
        elif path == '/api/radio':
            self.handle_radio(query)
        elif path == '/api/lyrics':
            self.handle_lyrics(query)
        elif path == '/icon.ico':
            # 支援根目錄圖示
            icon_path = os.path.join(BASE_DIR, 'icon.ico')
            if os.path.exists(icon_path):
                self.send_response(200)
                self.send_header('Content-Type', 'image/x-icon')
                self.end_headers()
                with open(icon_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            # 預設服務 web 目錄下的靜態網頁檔案
            super().do_GET()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_search(self, query):
        q = query.get('q', [''])[0].strip()
        multi = query.get('multi', ['0'])[0]
        if not q:
            self.send_json({'error': '缺少搜尋關鍵字'}, status=400)
            return

        if multi == '1':
            results = api_engine.search_multi(q, limit=8)
            self.send_json({'results': results})
        else:
            song = api_engine.search_song(q)
            if song:
                self.send_json({'song': song})
            else:
                self.send_json({'error': '找不到歌曲'}, status=404)

    def handle_stream(self, query):
        vid = query.get('vid', [''])[0].strip()
        title = query.get('title', [''])[0].strip()
        if not vid:
            self.send_json({'error': '缺少 video ID'}, status=400)
            return

        try:
            url = api_engine.stream(vid, song_title=title if title else None)
            self.send_json({'url': url})
        except Exception as e:
            self.send_json({'error': str(e)}, status=500)

    def handle_radio(self, query):
        vid = query.get('vid', [''])[0].strip()
        if not vid:
            self.send_json({'error': '缺少 video ID'}, status=400)
            return

        tracks = api_engine.radio(vid)
        self.send_json({'tracks': tracks})

    def handle_lyrics(self, query):
        title = query.get('title', [''])[0].strip()
        artist = query.get('artist', [''])[0].strip()
        if not title:
            self.send_json({'lyrics': {}})
            return

        lyrics = api_engine.lrclib(title, artist)
        self.send_json({'lyrics': lyrics})

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def main():
    port = int(os.environ.get('PORT', 8888))
    local_ip = get_local_ip()

    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, LynnRequestHandler)

    print("\n" + "=" * 55)
    print("🚀 Lynn-music 手機版伺服器已成功啟動！")
    print("=" * 55)
    print(f"💻 電腦本機測試網址:  http://localhost:{port}")
    print(f"📱 iPhone 手機開啟網址: http://{local_ip}:{port}")
    print("=" * 55)
    print("💡 使用方式：")
    print(f"1. 請確保手機與電腦連在同一個 Wi-Fi 網路")
    print(f"2. 手機開啟 Safari 瀏覽器，輸入上方的手機開啟網址")
    print("3. 點擊 Safari 下方「分享」按鈕，選擇「加入主畫面」即可像 App 一樣使用！")
    print("4. 若要停止伺服器，請按 Ctrl + C")
    print("=" * 55 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已安全停止。")

if __name__ == '__main__':
    main()
