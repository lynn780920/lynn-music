// Lynn-music Mobile Web Player
class LynnMobilePlayer {
  constructor() {
    this.audio = document.getElementById('audio-player');
    this.currentSong = null;
    this.queue = [];
    this.history = [];
    this.playedIds = new Set();
    this.lyrics = []; // [{ time: ms, text: '' }]
    this.favorites = this.loadFavorites();
    this.customPlaylists = this.loadCustomPlaylists();
    this.mode = 'RADIO'; // 'RADIO', 'SINGLE', 'LOOP'
    this.nextPreloadedStream = null;

    this.initElements();
    this.initEventListeners();
    this.initMediaSession();

    // 預設點一首開場歌曲
    const startSeeds = ['張惠妹 如果你也聽說', '周杰倫 說好不哭', '五月天 突然好想你', '蔡依林 倒帶', '陳奕迅 十年'];
    const chosen = startSeeds[Math.floor(Math.random() * startSeeds.length)];
    this.searchAndPlay(chosen);
  }

  initElements() {
    this.elSongTitle = document.getElementById('song-title');
    this.elSongArtist = document.getElementById('song-artist');
    this.elFavToggle = document.getElementById('btn-fav-toggle');
    this.elBtnAddPlaylist = document.getElementById('btn-add-playlist');
    this.elPlaylistsDrawer = document.getElementById('playlists-drawer');
    this.elPlaylistsList = document.getElementById('playlists-list');
    this.elAddPlaylistModal = document.getElementById('add-playlist-modal');
    this.elNewPlaylistName = document.getElementById('new-playlist-name');
    this.elBtnCreatePlaylistConfirm = document.getElementById('btn-create-playlist-confirm');
    this.elModalPlaylistOptions = document.getElementById('modal-playlist-options');

    this.elLyricsScroller = document.getElementById('lyrics-scroller');
    this.elProgressBar = document.getElementById('progress-bar');
    this.elCurrentTime = document.getElementById('current-time');
    this.elTotalTime = document.getElementById('total-time');
    this.elBtnPlay = document.getElementById('btn-play');
    this.elBtnPrev = document.getElementById('btn-prev');
    this.elBtnNext = document.getElementById('btn-next');
    this.elBtnMode = document.getElementById('btn-mode');
    this.elSearchInput = document.getElementById('search-input');
    this.elBtnSearch = document.getElementById('btn-search');
    this.elSearchResults = document.getElementById('search-results');
    this.elQueueDrawer = document.getElementById('queue-drawer');
    this.elQueueList = document.getElementById('queue-list');
    this.elFavDrawer = document.getElementById('fav-drawer');
    this.elFavList = document.getElementById('fav-list');
    this.elFavCount = document.getElementById('fav-count');
    this.elToast = document.getElementById('toast');
  }

  initEventListeners() {
    // 播放/暫停
    this.elBtnPlay.addEventListener('click', () => this.togglePlay());
    this.elBtnPrev.addEventListener('click', () => this.playPrev());
    this.elBtnNext.addEventListener('click', () => this.playNext());

    // 播放模式切換
    this.elBtnMode.addEventListener('click', () => this.toggleMode());

    // 進度條拖曳
    this.elProgressBar.addEventListener('input', (e) => {
      if (this.audio.duration) {
        this.audio.currentTime = (e.target.value / 100) * this.audio.duration;
      }
    });

    // Audio 播放事件
    this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
    this.audio.addEventListener('ended', () => this.onSongEnded());
    this.audio.addEventListener('play', () => { this.elBtnPlay.textContent = '⏸️'; });
    this.audio.addEventListener('pause', () => { this.elBtnPlay.textContent = '▶️'; });
    this.audio.addEventListener('error', (e) => {
      console.warn('音訊載入遇到錯誤，嘗試切換下一首...', e);
      this.showToast('⚠️ 串流錯誤，自動播下一首');
      setTimeout(() => this.playNext(), 1500);
    });

    // 我的最愛開關
    this.elFavToggle.addEventListener('click', () => this.toggleFavorite());

    // 自訂歌單按鈕與彈窗
    this.elBtnAddPlaylist.addEventListener('click', () => this.openAddPlaylistModal());
    document.getElementById('btn-modal-close').addEventListener('click', () => this.elAddPlaylistModal.classList.add('hidden'));
    this.elBtnCreatePlaylistConfirm.addEventListener('click', () => this.createAndAddToPlaylist());

    document.getElementById('btn-playlists-open').addEventListener('click', () => this.openPlaylistsDrawer());
    document.getElementById('btn-playlists-close').addEventListener('click', () => this.elPlaylistsDrawer.classList.add('hidden'));

    // 抽屜開關
    document.getElementById('btn-queue-open').addEventListener('click', () => this.openQueueDrawer());
    document.getElementById('btn-queue-close').addEventListener('click', () => this.elQueueDrawer.classList.add('hidden'));
    document.getElementById('btn-queue-shuffle').addEventListener('click', () => this.shuffleQueue());

    document.getElementById('btn-fav-list-open').addEventListener('click', () => this.openFavDrawer());
    document.getElementById('btn-fav-close').addEventListener('click', () => this.elFavDrawer.classList.add('hidden'));

    // 搜尋
    this.elBtnSearch.addEventListener('click', () => this.doSearch());
    this.elSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.doSearch();
    });

    // 點擊空白處隱藏搜尋結果
    document.addEventListener('click', (e) => {
      if (!this.elSearchInput.contains(e.target) && !this.elSearchResults.contains(e.target)) {
        this.elSearchResults.classList.add('hidden');
      }
    });
  }

  // ─── 🎧 iOS 鎖定畫面與後台多媒體控制 ───
  initMediaSession() {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.setActionHandler('play', () => this.audio.play());
      navigator.mediaSession.setActionHandler('pause', () => this.audio.pause());
      navigator.mediaSession.setActionHandler('previoustrack', () => this.playPrev());
      navigator.mediaSession.setActionHandler('nexttrack', () => this.playNext());
    }
  }

  updateMediaSession(title, artist) {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title,
        artist: artist,
        album: "Lynn's Music Player",
        artwork: [{ src: '/icon.ico', sizes: '128x128', type: 'image/x-icon' }]
      });
    }
  }

  // ─── 🔍 搜尋與播放 ───
  async doSearch() {
    const q = this.elSearchInput.value.trim();
    if (!q) return;
    this.showToast('🔍 搜尋中...');
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&multi=1`);
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        this.renderSearchResults(data.results);
      } else if (data.song) {
        this.loadAndPlaySong(data.song);
      } else {
        this.showToast('❌ 找不到歌曲');
      }
    } catch (e) {
      this.showToast('❌ 搜尋失敗: ' + e.message);
    }
  }

  renderSearchResults(songs) {
    this.elSearchResults.innerHTML = '';
    songs.forEach(s => {
      const div = document.createElement('div');
      div.className = 'search-item';
      div.innerHTML = `
        <div class="search-item-title">${s.title}</div>
        <div class="search-item-artist">${s.artist}</div>
      `;
      div.addEventListener('click', () => {
        this.elSearchResults.classList.add('hidden');
        this.elSearchInput.value = '';
        this.loadAndPlaySong(s);
      });
      this.elSearchResults.appendChild(div);
    });
    this.elSearchResults.classList.remove('hidden');
  }

  async searchAndPlay(keyword) {
    try {
      this.elSongTitle.textContent = `🔍 正在搜尋：${keyword}`;
      const res = await fetch(`/api/search?q=${encodeURIComponent(keyword)}`);
      const data = await res.json();
      if (data.song) {
        this.loadAndPlaySong(data.song);
      }
    } catch (e) {
      this.showToast('搜尋失敗');
    }
  }

  async loadAndPlaySong(song) {
    if (this.currentSong) {
      this.history.push(this.currentSong);
    }
    this.currentSong = song;
    this.playedIds.add(song.id);

    this.elSongTitle.textContent = song.title;
    this.elSongArtist.textContent = song.artist;
    this.updateFavButtonUI();
    this.updateMediaSession(song.title, song.artist);
    this.renderLyricsPlaceholder('⚡ 正在載入動態歌詞與音樂串流...');

    // 1. 取得音訊串流網址
    try {
      const streamRes = await fetch(`/api/stream?vid=${song.id}&title=${encodeURIComponent(song.title + ' ' + song.artist)}`);
      const streamData = await streamRes.json();
      if (streamData.url) {
        this.audio.src = streamData.url;
        this.audio.play().catch(() => console.log('Autoplay blocked until user interaction'));
      } else {
        throw new Error('無效音訊網址');
      }
    } catch (e) {
      this.showToast('⚠️ 解析音訊失敗，切換下一首');
      setTimeout(() => this.playNext(), 1500);
      return;
    }

    // 2. 平行非同步取得動態歌詞
    this.fetchLyrics(song.title, song.artist);

    // 3. 取得電台推薦 (若在 RADIO 模式)
    if (this.mode === 'RADIO') {
      this.fetchRadioQueue(song.id);
    }
  }

  async fetchLyrics(title, artist) {
    try {
      const res = await fetch(`/api/lyrics?title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}`);
      const data = await res.json();
      if (data.lyrics && Object.keys(data.lyrics).length > 0) {
        this.parseLyrics(data.lyrics);
      } else {
        this.renderLyricsPlaceholder('🎵 (純音樂 / 暫無動態歌詞)');
      }
    } catch (e) {
      this.renderLyricsPlaceholder('🎵 (純音樂 / 暫無動態歌詞)');
    }
  }

  parseLyrics(rawLyrics) {
    // rawLyrics: { "12000": "第一句歌詞", "15000": "第二句" }
    this.lyrics = Object.entries(rawLyrics)
      .map(([time, text]) => ({ time: parseInt(time), text }))
      .sort((a, b) => a.time - b.time);

    this.elLyricsScroller.innerHTML = '';
    this.lyrics.forEach((l, idx) => {
      const p = document.createElement('p');
      p.className = 'lyric-line';
      p.id = `lyric-${idx}`;
      p.textContent = l.text;
      this.elLyricsScroller.appendChild(p);
    });
  }

  renderLyricsPlaceholder(text) {
    this.lyrics = [];
    this.elLyricsScroller.innerHTML = `<p class="lyric-line active">${text}</p>`;
  }

  async fetchRadioQueue(vid) {
    try {
      const res = await fetch(`/api/radio?vid=${vid}`);
      const data = await res.json();
      if (data.tracks && data.tracks.length > 0) {
        // 過濾已播放與現有佇列
        const existingIds = new Set(this.queue.map(s => s.id));
        data.tracks.forEach(t => {
          if (!this.playedIds.has(t.id) && !existingIds.has(t.id)) {
            this.queue.push(t);
            existingIds.add(t.id);
          }
        });
        if (this.queue.length > 40) this.queue = this.queue.slice(0, 40);
        this.renderQueueUI();
      }
    } catch (e) {
      console.log('取得電台失敗', e);
    }
  }

  // ─── ⏰ 播放更新與動態歌詞捲動 ───
  onTimeUpdate() {
    if (!this.audio.duration) return;

    const cur = this.audio.currentTime;
    const dur = this.audio.duration;

    // 更新進度條與時間標籤
    const pct = (cur / dur) * 100;
    this.elProgressBar.value = pct;
    this.elCurrentTime.textContent = this.formatTime(cur);
    this.elTotalTime.textContent = this.formatTime(dur);

    // 智慧鎖屏換歌預先快取：當播到 85% 時，預先向後端請求下一首串流網址
    if (pct > 85 && !this.nextPreloadedStream && this.queue.length > 0) {
      const nextSong = this.queue[0];
      fetch(`/api/stream?vid=${nextSong.id}&title=${encodeURIComponent(nextSong.title + ' ' + nextSong.artist)}`)
        .then(r => r.json())
        .then(data => { if (data.url) this.nextPreloadedStream = data.url; })
        .catch(() => {});
    }

    // 更新動態歌詞高亮
    if (this.lyrics.length > 0) {
      const curMs = cur * 1000;
      let activeIdx = -1;
      for (let i = 0; i < this.lyrics.length; i++) {
        if (curMs >= this.lyrics[i].time) {
          activeIdx = i;
        } else {
          break;
        }
      }

      if (activeIdx >= 0) {
        document.querySelectorAll('.lyric-line').forEach((el, idx) => {
          if (idx === activeIdx) {
            if (!el.classList.contains('active')) {
              el.classList.add('active');
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          } else {
            el.classList.remove('active');
          }
        });
      }
    }
  }

  onSongEnded() {
    if (this.mode === 'SINGLE') {
      this.audio.currentTime = 0;
      this.audio.play();
    } else {
      this.playNext();
    }
  }

  togglePlay() {
    if (this.audio.paused) {
      this.audio.play();
    } else {
      this.audio.pause();
    }
  }

  playNext() {
    this.nextPreloadedStream = null;
    if (this.queue.length > 0) {
      const next = this.queue.shift();
      this.renderQueueUI();
      this.loadAndPlaySong(next);
    } else if (this.currentSong) {
      this.searchAndPlay(this.currentSong.title + ' ' + this.currentSong.artist);
    }
  }

  playPrev() {
    if (this.history.length > 0) {
      const prev = this.history.pop();
      this.loadAndPlaySong(prev);
    }
  }

  toggleMode() {
    if (this.mode === 'RADIO') {
      this.mode = 'SINGLE';
      this.elBtnMode.textContent = '🔂 單曲';
      this.showToast('模式：單曲循環');
    } else if (this.mode === 'SINGLE') {
      this.mode = 'LOOP';
      this.elBtnMode.textContent = '🔁 佇列';
      this.showToast('模式：佇列循環');
    } else {
      this.mode = 'RADIO';
      this.elBtnMode.textContent = '🔄 電台';
      this.showToast('模式：隨機電台');
    }
  }

  formatTime(secs) {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  // ─── ❤️ 我的最愛 (localStorage) ───
  loadFavorites() {
    try {
      const data = localStorage.getItem('lynn_favorites');
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  }

  saveFavorites() {
    localStorage.setItem('lynn_favorites', JSON.stringify(this.favorites));
    this.elFavCount.textContent = this.favorites.length;
    this.updateFavButtonUI();
  }

  isFavorite(vid) {
    return this.favorites.some(f => f.id === vid);
  }

  toggleFavorite() {
    if (!this.currentSong) return;
    const vid = this.currentSong.id;
    const idx = this.favorites.findIndex(f => f.id === vid);
    if (idx >= 0) {
      this.favorites.splice(idx, 1);
      this.showToast('🤍 已移出我的最愛');
    } else {
      this.favorites.push({ ...this.currentSong });
      this.showToast('❤️ 已加入我的最愛');
    }
    this.saveFavorites();
  }

  updateFavButtonUI() {
    if (!this.currentSong) {
      this.elFavToggle.textContent = '🤍';
      return;
    }
    this.elFavToggle.textContent = this.isFavorite(this.currentSong.id) ? '❤️' : '🤍';
  }

  // ─── 📂 自訂歌單 (localStorage: lynn_custom_playlists) ───
  loadCustomPlaylists() {
    try {
      const data = localStorage.getItem('lynn_custom_playlists');
      return data ? JSON.parse(data) : {};
    } catch {
      return {};
    }
  }

  saveCustomPlaylists() {
    localStorage.setItem('lynn_custom_playlists', JSON.stringify(this.customPlaylists));
  }

  openAddPlaylistModal() {
    if (!this.currentSong) {
      this.showToast('⚠️ 目前沒有正在播放的歌曲');
      return;
    }
    this.elNewPlaylistName.value = '';
    this.renderModalPlaylistOptions();
    this.elAddPlaylistModal.classList.remove('hidden');
  }

  renderModalPlaylistOptions() {
    this.elModalPlaylistOptions.innerHTML = '';
    const playlistNames = Object.keys(this.customPlaylists);
    if (playlistNames.length === 0) {
      this.elModalPlaylistOptions.innerHTML = '<p style="text-align:center; color:#777; font-size:12px; padding:10px;">尚未建立任何自訂歌單</p>';
      return;
    }
    playlistNames.forEach(name => {
      const btn = document.createElement('button');
      btn.className = 'modal-pl-btn';
      const count = this.customPlaylists[name].length;
      btn.innerHTML = `<span>📁 ${name}</span><span style="font-size:12px; color:#00e5ff;">(${count} 首)</span>`;
      btn.addEventListener('click', () => {
        this.addSongToPlaylist(name, this.currentSong);
        this.elAddPlaylistModal.classList.add('hidden');
      });
      this.elModalPlaylistOptions.appendChild(btn);
    });
  }

  createAndAddToPlaylist() {
    const name = this.elNewPlaylistName.value.trim();
    if (!name) {
      this.showToast('⚠️ 請輸入歌單名稱');
      return;
    }
    if (!this.customPlaylists[name]) {
      this.customPlaylists[name] = [];
    }
    this.addSongToPlaylist(name, this.currentSong);
    this.elAddPlaylistModal.classList.add('hidden');
  }

  addSongToPlaylist(playlistName, song) {
    if (!this.customPlaylists[playlistName]) {
      this.customPlaylists[playlistName] = [];
    }
    const list = this.customPlaylists[playlistName];
    if (list.some(s => s.id === song.id)) {
      this.showToast(`⚠️ 歌曲已在「${playlistName}」中`);
      return;
    }
    list.push({ ...song });
    this.saveCustomPlaylists();
    this.showToast(`✔ 已加入「${playlistName}」`);
  }

  openPlaylistsDrawer() {
    this.renderPlaylistsDrawer();
    this.elPlaylistsDrawer.classList.remove('hidden');
  }

  renderPlaylistsDrawer() {
    this.elPlaylistsList.innerHTML = '';
    const playlistNames = Object.keys(this.customPlaylists);
    if (playlistNames.length === 0) {
      this.elPlaylistsList.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">尚無自訂歌單，點擊「➕」按鈕即可新增！</p>';
      return;
    }

    playlistNames.forEach(name => {
      const songs = this.customPlaylists[name];
      const card = document.createElement('div');
      card.className = 'playlist-card';

      card.innerHTML = `
        <div class="playlist-card-header">
          <div>
            <span class="playlist-card-title">📁 ${name}</span>
            <span class="playlist-card-count">(${songs.length} 首)</span>
          </div>
          <div class="playlist-card-actions">
            <button class="btn-sm btn-play-pl">▶️ 播放整張</button>
            <button class="btn-sm btn-del-pl" style="color:#ff5252;">🗑️</button>
          </div>
        </div>
        <div class="playlist-songs-list hidden"></div>
      `;

      const header = card.querySelector('.playlist-card-header');
      const songsList = card.querySelector('.playlist-songs-list');
      const btnPlayAll = card.querySelector('.btn-play-pl');
      const btnDelPl = card.querySelector('.btn-del-pl');

      // 展開/收合
      header.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        songsList.classList.toggle('hidden');
      });

      // 播放整張歌單
      btnPlayAll.addEventListener('click', (e) => {
        e.stopPropagation();
        if (songs.length === 0) {
          this.showToast('⚠️ 歌單內目前沒有歌曲');
          return;
        }
        this.queue = [...songs.slice(1)];
        this.renderQueueUI();
        this.elPlaylistsDrawer.classList.add('hidden');
        this.loadAndPlaySong(songs[0]);
        this.showToast(`🚀 正在播放歌單「${name}」`);
      });

      // 刪除整張歌單
      btnDelPl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm(`確定要刪除整個歌單「${name}」嗎？`)) {
          delete this.customPlaylists[name];
          this.saveCustomPlaylists();
          this.renderPlaylistsDrawer();
          this.showToast(`🗑️ 已刪除歌單「${name}」`);
        }
      });

      // 渲染歌單內的每一首歌
      if (songs.length === 0) {
        songsList.innerHTML = '<p style="font-size:12px; color:#666; padding:8px;">(空歌單)</p>';
      } else {
        songs.forEach((s, sIdx) => {
          const sItem = document.createElement('div');
          sItem.className = 'list-item';
          sItem.innerHTML = `
            <div class="list-item-info">
              <div class="list-item-title">${sIdx + 1}. ${s.title}</div>
              <div class="list-item-artist">${s.artist}</div>
            </div>
            <button class="list-item-del" title="移出">✕</button>
          `;
          sItem.querySelector('.list-item-info').addEventListener('click', () => {
            this.elPlaylistsDrawer.classList.add('hidden');
            this.loadAndPlaySong(s);
          });
          sItem.querySelector('.list-item-del').addEventListener('click', (ev) => {
            ev.stopPropagation();
            songs.splice(sIdx, 1);
            this.saveCustomPlaylists();
            this.renderPlaylistsDrawer();
          });
          songsList.appendChild(sItem);
        });
      }

      this.elPlaylistsList.appendChild(card);
    });
  }

  openFavDrawer() {
    this.elFavList.innerHTML = '';
    this.elFavCount.textContent = this.favorites.length;
    if (this.favorites.length === 0) {
      this.elFavList.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">尚無收藏歌曲</p>';
    } else {
      this.favorites.forEach((song, idx) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `
          <div class="list-item-info">
            <div class="list-item-title">${song.title}</div>
            <div class="list-item-artist">${song.artist}</div>
          </div>
          <button class="list-item-del" title="刪除">🗑️</button>
        `;
        item.querySelector('.list-item-info').addEventListener('click', () => {
          this.elFavDrawer.classList.add('hidden');
          this.loadAndPlaySong(song);
        });
        item.querySelector('.list-item-del').addEventListener('click', (e) => {
          e.stopPropagation();
          this.favorites.splice(idx, 1);
          this.saveFavorites();
          this.openFavDrawer();
        });
        this.elFavList.appendChild(item);
      });
    }
    this.elFavDrawer.classList.remove('hidden');
  }

  // ─── 📜 即將播放佇列 ───
  openQueueDrawer() {
    this.renderQueueUI();
    this.elQueueDrawer.classList.remove('hidden');
  }

  renderQueueUI() {
    this.elQueueList.innerHTML = '';
    if (this.queue.length === 0) {
      this.elQueueList.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">佇列目前為空</p>';
      return;
    }
    this.queue.forEach((song, idx) => {
      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <div class="list-item-info">
          <div class="list-item-title">${idx + 1}. ${song.title}</div>
          <div class="list-item-artist">${song.artist}</div>
        </div>
        <button class="list-item-del" title="移出">✕</button>
      `;
      item.querySelector('.list-item-info').addEventListener('click', () => {
        this.elQueueDrawer.classList.add('hidden');
        this.queue.splice(idx, 1);
        this.loadAndPlaySong(song);
      });
      item.querySelector('.list-item-del').addEventListener('click', (e) => {
        e.stopPropagation();
        this.queue.splice(idx, 1);
        this.renderQueueUI();
      });
      this.elQueueList.appendChild(item);
    });
  }

  shuffleQueue() {
    for (let i = this.queue.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [this.queue[i], this.queue[j]] = [this.queue[j], this.queue[i]];
    }
    this.renderQueueUI();
    this.showToast('🔀 佇列已打亂');
  }

  showToast(msg) {
    this.elToast.textContent = msg;
    this.elToast.classList.remove('hidden');
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.elToast.classList.add('hidden');
    }, 1800);
  }
}

// 啟動播放器
window.addEventListener('DOMContentLoaded', () => {
  window.player = new LynnMobilePlayer();
});
