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

DIVERSE_POPULAR_ARTISTS = [
    '周杰倫', '告五人', '韋禮安', '五月天', '鄧紫棋', 
    '蔡依林', '林俊傑', '張惠妹', '陳奕迅', '孫燕姿', 
    '梁靜茹', '田馥甄', '盧廣仲', '徐佳瑩', '莫文蔚', 
    '李榮浩', '伍佰', '八三夭', '理想混蛋', '動力火車', 
    '蘇打綠', '楊丞琳', '蕭敬騰', '陶喆', '王力宏', 
    '草東沒有派對', '落日飛車', '茄子蛋', '戴佩妮', '丁噹', 
    '艾怡良', '郁可唯', '頑童MJ116', '瘦子E.SO', '高爾宣', 
    '美秀集團', '麋先生', '宇宙人', '滅火器', '李聖傑', 
    '林宥嘉', '蕭煌奇', '汪蘇瀧', '張震嶽', '信樂團', 
    '張韶涵', '王心凌', '潘瑋柏', '光良', '品冠'
]

class MusicAPI:
    def __init__(self):
        self.yt = YTMusic()
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }

    @staticmethod
    def is_spam_title(title):
        bad_keywords = [
            '最好听', '最好聽', '合輯', '合集', '串燒', '串烧',
            '首催淚', '首催泪', '首傷感', '首伤感', '連續播放', '连续播放',
            '精選輯', '精选集', '小時', '小时', '必聽', '熱門榜', '排行榜',
            '催淚傷感', '伤感情歌', '情歌精選'
        ]
        return any(k in title for k in bad_keywords)

    def search_song(self, text):
        try:
            r = self.yt.search(text, filter='songs')
            if not r:
                r = self.yt.search(text, filter='videos')
            if not r:
                return None
            for s in r:
                if not self.is_spam_title(s.get('title', '')):
                    return {
                        'id': s['videoId'],
                        'title': s['title'],
                        'artist': s['artists'][0]['name'] if s.get('artists') else '未知歌手'
                    }
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
            for item in r:
                if 'videoId' in item:
                    title = item.get('title', '未知曲名')
                    if self.is_spam_title(title):
                        continue
                    results.append({
                        'id': item['videoId'],
                        'title': title,
                        'artist': item['artists'][0]['name'] if item.get('artists') else '未知歌手'
                    })
                    if len(results) >= limit:
                        break
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

    def generate_diverse_queue(self, limit=25, exclude_artist=''):
        """隨機生成絕不重複歌手的電台佇列（每位歌手在清單中僅出現 1 首）"""
        seen_artists = set()
        if exclude_artist and exclude_artist != '未知歌手':
            seen_artists.add(exclude_artist.lower().strip())

        candidates = [a for a in DIVERSE_POPULAR_ARTISTS if a.lower().strip() not in seen_artists]
        random.shuffle(candidates)

        tracks = []
        for art in candidates:
            if len(tracks) >= limit:
                break
            song = self.search_song(art)
            if song and song.get('id'):
                tracks.append(song)
                seen_artists.add(art.lower().strip())

        random.shuffle(tracks)
        return tracks

    def radio(self, vid, artist='', title='', limit=25):
        """
        電台推薦歌曲產生器：
        採用「嚴格單一歌手限制 (Strict 1 Song Per Artist) + 隨機多樣性補足」，
        保證即將播放清單中每首歌均為完全不同的歌手，徹底杜絕同一歌手重複霸榜。
        """
        seen_ids = {vid}
        seen_artists = set()
        cur_art = (artist or '').lower().strip()
        if cur_art and cur_art != '未知歌手':
            seen_artists.add(cur_art)

        tracks = []

        # 1. 嘗試由 YouTube Music get_watch_playlist 取得官方推薦（每位歌手嚴格只取 1 首）
        try:
            data = self.yt.get_watch_playlist(vid)
            for i in data.get('tracks', []):
                item_id = i.get('videoId')
                if not item_id or item_id in seen_ids:
                    continue
                art = i['artists'][0]['name'] if i.get('artists') else '未知歌手'
                clean_art = art.lower().strip()
                if clean_art in seen_artists or clean_art == '未知歌手':
                    continue
                title_item = i.get('title', '未知歌曲')
                if self.is_spam_title(title_item):
                    continue

                tracks.append({
                    'title': title_item,
                    'artist': art,
                    'id': item_id
                })
                seen_artists.add(clean_art)
                seen_ids.add(item_id)
                if len(tracks) >= limit:
                    break
        except Exception:
            pass

        # 2. 若推薦筆數不足，以隨機多元熱門歌手補足（每位歌手嚴格只取 1 首）
        if len(tracks) < limit:
            needed = limit - len(tracks)
            cand_pool = [a for a in DIVERSE_POPULAR_ARTISTS if a.lower().strip() not in seen_artists]
            random.shuffle(cand_pool)
            for cand_art in cand_pool[:needed + 5]:
                if len(tracks) >= limit:
                    break
                try:
                    song = self.search_song(cand_art)
                    if song and song.get('id') and song['id'] not in seen_ids:
                        tracks.append(song)
                        seen_artists.add(cand_art.lower().strip())
                        seen_ids.add(song['id'])
                except Exception:
                    pass

        # 3. 全隨機打散，確保排列完全非單一歌手壟斷
        random.shuffle(tracks)
        return tracks

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
