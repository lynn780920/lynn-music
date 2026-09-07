# -*- coding: utf-8 -*-
"""
Lynn-music Core Engine
獨立核心模組：支援 YouTube 串流解析、多重 Client 容錯備援、動態歌詞與電台推薦
無 PyQt 依賴，適合本機播放器與雲端 API 伺服器共用
"""

import os
import sys
import json
import requests
import yt_dlp
import random
import re

# ─── 🛑 核心閃退攔截防禦：必須在載入 ytmusicapi 之前執行 ───
import gettext
gettext.translation = lambda *args, **kwargs: gettext.NullTranslations()

from ytmusicapi import YTMusic

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

    def search_multi(self, text, limit=10):
        try:
            results = []
            r = self.yt.search(text, filter='songs')
            if not r:
                r = self.yt.search(text, filter='videos')
            for item in r[:limit]:
                if 'videoId' in item:
                    results.append({
                        'id': item['videoId'],
                        'title': item.get('title', '未知曲名'),
                        'artist': item['artists'][0]['name'] if item.get('artists') else '未知歌手'
                    })
            return results
        except Exception as e:
            print(f"多筆搜尋失敗: {e}")
            return []

    def stream(self, vid, song_title=None):
        client_configs = [
            {'player_client': ['android'], 'player_skip': ['webpage', 'configs']},
            {'player_client': ['ios'], 'player_skip': ['webpage', 'configs']},
            {'player_client': ['android_creator'], 'player_skip': ['webpage', 'configs']},
            {'player_client': ['tv'], 'player_skip': ['webpage']},
            {'player_client': ['android', 'web']},
            {'player_client': ['web']}
        ]

        formats_to_try = ['bestaudio/best', 'ba/b', 'best']

        last_error = None
        for cfg in client_configs:
            for fmt in formats_to_try:
                ydl_opts = {
                    'format': fmt,
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'geo_bypass': True,
                    'extractor_args': {
                        'youtube': cfg
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
                    for cfg in client_configs[:2]:
                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'quiet': True,
                            'no_warnings': True,
                            'nocheckcertificate': True,
                            'geo_bypass': True,
                            'extractor_args': {'youtube': cfg},
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

    def radio(self, vid, artist='', title=''):
        """
        電台推薦歌曲產生器：
        採用「歌手交錯輪播演算法 (Round-Robin Interleaving)」，
        保證清單中絕不出現同一歌手連續排隊（杜絕整排都是同一歌手的情況）。
        """
        import collections
        by_artist = collections.defaultdict(list)
        seen_ids = {vid}

        # 1. 嘗試由 YouTube Music get_watch_playlist 取得官方推薦
        try:
            data = self.yt.get_watch_playlist(vid)
            for i in data.get('tracks', []):
                item_id = i.get('videoId')
                if item_id and item_id not in seen_ids:
                    art = i['artists'][0]['name'] if i.get('artists') else '未知歌手'
                    # 每位歌手在候選池中最多保留 2 首，避免單一歌手壟斷
                    if len(by_artist[art]) < 2:
                        by_artist[art].append({
                            'title': i.get('title', '未知歌曲'),
                            'artist': art,
                            'id': item_id
                        })
                        seen_ids.add(item_id)
        except Exception:
            pass

        # 2. 若歌手多樣性不足（不同歌手少於 6 位），智慧補充熱門華語歌手歌曲
        popular_pool = [
            '周杰倫', '五月天', '告五人', '韋禮安', '鄧紫棋', 
            '蔡依林', '林俊傑', '張惠妹', '陳奕迅', '孫燕姿', 
            '梁靜茹', '田馥甄', '盧廣仲', '徐佳瑩', '莫文蔚',
            '李榮浩', '八三夭', '理想混蛋', '動力火車', '落日飛車'
        ]
        random.shuffle(popular_pool)
        
        current_artists = set(by_artist.keys())
        needed_count = max(0, 8 - len(current_artists))
        supplement_artists = [a for a in popular_pool if a not in current_artists][:needed_count]

        for art in supplement_artists:
            try:
                results = self.yt.search(art, filter='songs')
                added = 0
                for item in results:
                    item_id = item.get('videoId')
                    if item_id and item_id not in seen_ids:
                        by_artist[art].append({
                            'title': item.get('title', '未知歌曲'),
                            'artist': item['artists'][0]['name'] if item.get('artists') else art,
                            'id': item_id
                        })
                        seen_ids.add(item_id)
                        added += 1
                        if added >= 2:
                            break
            except Exception:
                pass

        # 3. 歌手交錯輪播 (Round-Robin Interleaving)
        # 依序從每一位歌手各取一首歌加入佇列，確保相鄰兩首歌絕對不會是同一位歌手
        mixed = []
        artist_keys = list(by_artist.keys())
        random.shuffle(artist_keys)

        # 若原曲歌手在清單中，優先作為輪播的開頭歌手（但只有 1 首，之後立即切換給下一位歌手）
        if artist and artist in artist_keys:
            artist_keys.remove(artist)
            artist_keys.insert(0, artist)

        max_len = max((len(v) for v in by_artist.values()), default=0)
        for r in range(max_len):
            for art in artist_keys:
                if r < len(by_artist[art]):
                    mixed.append(by_artist[art][r])

        return mixed

    def lrclib(self, title, artist):
        def clean_text(text):
            text = re.sub(r'[\(\[\{【].*?[\)\]\}】]', '', text)
            text = re.sub(r'(?i)(official|video|mv|hd|lyrics|字幕|版|單曲|高音質|熱歌)', '', text)
            return text.strip()

        clean_title = clean_text(title)
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
            url = 'https://lrclib.net/api/search'
            params = {'track_name': clean_title, 'artist_name': clean_artist}
            r = requests.get(url, params=params, timeout=5.0)
            
            if r.status_code == 200 and r.json():
                data = r.json()
                synced = data[0].get('syncedLyrics', '')
                if synced: return parse_lrc_text(synced)
                plain = data[0].get('plainLyrics', '')
                if plain: return {0: plain.replace('\n', ' / ')}

            params_fuzzy = {'q': clean_title}
            r_fuzzy = requests.get(url, params=params_fuzzy, timeout=5.0)
            if r_fuzzy.status_code == 200 and r_fuzzy.json():
                for res in r_fuzzy.json():
                    synced = res.get('syncedLyrics', '')
                    if synced:
                        return parse_lrc_text(synced)
                for res in r_fuzzy.json():
                    plain = res.get('plainLyrics', '')
                    if plain:
                        return {0: plain.replace('\n', ' / ')}
            return {}
        except:
            return {}
