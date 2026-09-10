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
    # 華語歌壇天王天后
    '周杰倫', '林俊傑', '陳奕迅', '蔡依林', '張惠妹', '王菲', '孫燕姿', '梁靜茹', 
    '蕭亞軒', '莫文蔚', '田馥甄', 'S.H.E', '王力宏', '陶喆', '潘瑋柏', '楊丞琳', 
    '張韶涵', '王心凌', '李榮浩', '薛之謙', '鄧紫棋', '華晨宇', '汪蘇瀧', '毛不易',
    
    # 經典傳奇唱將
    '伍佰', '李宗盛', '羅大佑', '張學友', '劉德華', '黎明', '郭富城', '信樂團', 
    '動力火車', '迪克牛仔', '齊秦', '張宇', '游鴻明', '伍思凱', '張雨生', '趙傳', 
    '任賢齊', '周華健', '陶晶瑩', '張震嶽', '庾澄慶', '黃品源', '杜德偉', '王傑',
    
    # 抒情天后與金曲歌后
    '戴佩妮', '蔡健雅', '范瑋琪', '梁詠琪', '許茹芸', '彭佳慧', '溫嵐', '辛曉琪', 
    '萬芳', '蘇慧倫', '許美靜', '順子', '郁可唯', '丁噹', '家家', '白安', 
    '郭靜', '曾沛慈', 'A-Lin', '閻奕格', '孫盛希', '洪佩瑜',
    
    # 實力派唱作男歌手
    '韋禮安', '盧廣仲', '林宥嘉', '徐佳瑩', '艾怡良', '蕭敬騰', '方大同', '吳青峰', 
    '蘇打綠', '李聖傑', '品冠', '光良', '曹格', '阿杜', '蕭煌奇', '胡夏', 
    '嚴爵', '畢書盡', '李友廷', '柏霖', '持修', '壞特?te', '鄭興',
    
    # 人氣樂團與獨立樂隊
    '五月天', '滅火器', '草東沒有派對', '落日飛車', '茄子蛋', '美秀集團', '麋先生', 
    '宇宙人', '八三夭', '理想混蛋', '脆樂團', '告五人', '芒果醬', '溫蒂漫步', 
    '冰球樂團', '甜約翰', '溫室雜草', '好樂團', '守夜人', '荷爾蒙少年', '椅子樂團', 
    '拍謝少年', '傻子與白痴', '康士坦的變化球', '老王樂隊', '旺福', '怕胖團',
    
    # 嘻哈、R&B 與潮流都會
    '頑童MJ116', '瘦子E.SO', '高爾宣', '熊仔', '熱狗MC HotDog', '蛋堡', '國蛋', 
    'Leo王', 'ØZI', '9m88', 'J.Sheon', 'Karencici', '周湯豪', '派偉俊', '玖壹壹',
    
    # 療癒民謠與熱門新聲
    '承桓', '菲道爾', '任然', '于文文', '隊長', '顏人中', '房東的貓', '永彬Ryan.B', 
    '王貳浪', '焦邁奇', '阿冗', '藍心羽', '井朧', '是七叔呢'
]

POPULAR_DISCOVERY_THEMES = [
    '華語流行新歌',
    '台灣熱門單曲',
    '經典華語金曲',
    '2000年代華語金曲',
    '90年代華語經典',
    'KKBOX 華語單曲',
    'KTV 必點華語排行',
    '華語抒情慢歌',
    '華語熱門流行歌',
    '台灣流行金曲'
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

    def search_random_song(self, text):
        """搜尋某藝人或主題，並隨機挑選其排名前列的代表性歌曲（而非每次都固定返回第一首）"""
        try:
            r = self.yt.search(text, filter='songs')
            if not r:
                r = self.yt.search(text, filter='videos')
            if not r:
                return None
            valid = []
            for s in r[:8]:
                title = s.get('title', '')
                if not self.is_spam_title(title) and 'videoId' in s:
                    valid.append({
                        'id': s['videoId'],
                        'title': title,
                        'artist': s['artists'][0]['name'] if s.get('artists') else text
                    })
            if valid:
                return random.choice(valid)
            return None
        except Exception as e:
            print(f"隨機搜尋歌曲失敗 ({text}): {e}")
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

    def generate_diverse_queue(self, limit=25, exclude_artist='', exclude_artists=None):
        """
        隨機生成絕不重複歌手的多元電台佇列：
        結合探索熱門主題即時搜尋 + 140+ 華語實力歌手代表作隨機選曲，
        確保每次刷新均呈現截然不同的全新曲庫，徹底杜絕「每次點選都差不多」的問題。
        """
        seen_artists = set()
        if exclude_artist and exclude_artist != '未知歌手':
            seen_artists.add(exclude_artist.lower().strip())

        if exclude_artists:
            for ea in exclude_artists:
                c = ea.lower().strip()
                if c and c != '未知歌手':
                    seen_artists.add(c)

        tracks = []
        seen_ids = set()

        # 1. 隨機抽選 2 個不同熱門華語主題進行探索搜尋（快速獲取 20+ 首不同藝人的熱播金曲）
        chosen_themes = random.sample(POPULAR_DISCOVERY_THEMES, 2)
        for theme in chosen_themes:
            if len(tracks) >= limit:
                break
            try:
                results = self.yt.search(theme, filter='songs')
                random.shuffle(results)
                for item in results:
                    item_id = item.get('videoId')
                    if not item_id or item_id in seen_ids:
                        continue
                    art = item['artists'][0]['name'] if item.get('artists') else '未知歌手'
                    clean_art = art.lower().strip()
                    if clean_art in seen_artists or clean_art == '未知歌手':
                        continue
                    title_item = item.get('title', '未知歌曲')
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
            except Exception as e:
                print(f"探索主題搜尋異常 ({theme}): {e}")

        # 2. 若筆數尚未達到 limit，從 140+ 實力藝人庫中隨機挑選（每位歌手隨機抽樣熱門非重複單曲）
        if len(tracks) < limit:
            candidates = [a for a in DIVERSE_POPULAR_ARTISTS if a.lower().strip() not in seen_artists]
            random.shuffle(candidates)
            needed = limit - len(tracks)
            for art in candidates[:needed + 5]:
                if len(tracks) >= limit:
                    break
                song = self.search_random_song(art)
                if song and song.get('id') and song['id'] not in seen_ids:
                    tracks.append(song)
                    seen_artists.add(art.lower().strip())
                    seen_ids.add(song['id'])

        # 3. 極端保護：若候選名單耗盡仍不足 limit，放寬已排除藝人隨機補充其未播放過的其他歌曲
        if len(tracks) < limit:
            fallback = list(DIVERSE_POPULAR_ARTISTS)
            random.shuffle(fallback)
            for art in fallback:
                if len(tracks) >= limit:
                    break
                clean_art = art.lower().strip()
                if clean_art in seen_artists:
                    continue
                song = self.search_random_song(art)
                if song and song.get('id') and song['id'] not in seen_ids:
                    tracks.append(song)
                    seen_artists.add(clean_art)
                    seen_ids.add(song['id'])

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

        # 2. 若推薦筆數不足，以隨機多元熱門歌手補足（每位歌手嚴格只取 1 首，且隨機抽樣熱門曲）
        if len(tracks) < limit:
            needed = limit - len(tracks)
            cand_pool = [a for a in DIVERSE_POPULAR_ARTISTS if a.lower().strip() not in seen_artists]
            random.shuffle(cand_pool)
            for cand_art in cand_pool[:needed + 5]:
                if len(tracks) >= limit:
                    break
                try:
                    song = self.search_random_song(cand_art)
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
