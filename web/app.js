// Lynn-music Mobile Cloud Web Player
// 採用 YouTube 官方播放引擎 (100% 雲端動態運行、免開電腦、永不被機房封鎖)

// 🌟 熱門華語實力派藝人種子庫（開局隨機挑選藝人，每次打開都完全不同，絕不重複）
const POPULAR_ARTISTS = [
  '周杰倫', '林俊傑', '陳奕迅', '蔡依林', '張惠妹', '王菲', '孫燕姿', '梁靜茹', 
  '蕭亞軒', '莫文蔚', '田馥甄', 'S.H.E', '王力宏', '陶喆', '潘瑋柏', '楊丞琳', 
  '張韶涵', '王心凌', '李榮浩', '薛之謙', '鄧紫棋', '華晨宇', '汪蘇瀧', '毛不易',
  '伍佰', '李宗盛', '羅大佑', '張學友', '劉德華', '黎明', '郭富城', '信樂團', 
  '動力火車', '迪克牛仔', '齊秦', '張宇', '游鴻明', '伍思凱', '張雨生', '趙傳', 
  '任賢齊', '周華健', '陶晶瑩', '張震嶽', '庾澄慶', '黃品源', '杜德偉', '王傑',
  '戴佩妮', '蔡健雅', '范瑋琪', '梁詠琪', '許茹芸', '彭佳慧', '溫嵐', '辛曉琪', 
  '萬芳', '蘇慧倫', '許美靜', '順子', '郁可唯', '丁噹', '家家', '白安', 
  '郭靜', '曾沛慈', 'A-Lin', '閻奕格', '孫盛希', '洪佩瑜',
  '韋禮安', '盧廣仲', '林宥嘉', '徐佳瑩', '艾怡良', '蕭敬騰', '方大同', '吳青峰', 
  '蘇打綠', '李聖傑', '品冠', '光良', '曹格', '阿杜', '蕭煌奇', '胡夏', 
  '嚴爵', '畢書盡', '李友廷', '柏霖', '持修', '壞特?te', '鄭興',
  '五月天', '滅火器', '草東沒有派對', '落日飛車', '茄子蛋', '美秀集團', '麋先生', 
  '宇宙人', '八三夭', '理想混蛋', '脆樂團', '告五人', '芒果醬', '溫蒂漫步', 
  '冰球樂團', '甜約翰', '溫室雜草', '好樂團', '守夜人', '荷爾蒙少年', '椅子樂團', 
  '拍謝少年', '傻子與白痴', '康士坦的變化球', '老王樂隊', '旺福', '怕胖團',
  '頑童MJ116', '瘦子E.SO', '高爾宣', '熊仔', '熱狗MC HotDog', '蛋堡', '國蛋', 
  'Leo王', 'ØZI', '9m88', 'J.Sheon', 'Karencici', '周湯豪', '派偉俊', '玖壹壹',
  '承桓', '菲道爾', '任然', '于文文', '隊長', '顏人中', '房東的貓', '永彬Ryan.B', 
  '王貳浪', '焦邁奇', '阿冗', '藍心羽', '井朧', '是七叔呢'
];

class LynnMobilePlayer {
  constructor() {
    this.ytPlayer = null;
    this.isYTReady = false;
    this.pendingSong = null;
    this.isSwitchingTrack = false;
    this.lastErrorTime = 0;

    this.currentSong = null;
    this.queue = [];
    this.history = [];
    this.playedIds = new Set();
    this.lyrics = []; // [{ time: ms, text: '' }]
    this.favorites = this.loadFavorites();
    this.customPlaylists = this.loadCustomPlaylists();
    this.mode = 'RADIO'; // 'RADIO', 'SINGLE', 'LOOP'
    this.wakeLock = null;

    this.initElements();
    this.initEventListeners();
    this.initMediaSession();

    // 🌟 依照熱門藝人庫隨機產出開場歌曲，每次進入都耳目一新
    this.initRandomPopularArtist();
  }

  getRandomArtist() {
    return POPULAR_ARTISTS[Math.floor(Math.random() * POPULAR_ARTISTS.length)];
  }

  async initRandomPopularArtist() {
    this.elSongTitle.textContent = '正在為您精選熱門電台...';
    this.elSongArtist.textContent = '雲端熱門曲庫載入中...';

    // 1. 優先嘗試從雲端 /api/trending 取得（後端隨機挑選熱門藝人，並已交叉混編 30+ 首不同藝人的電台）
    try {
      const res = await fetch('/api/trending');
      const data = await res.json();
      if (data.startSong) {
        this.queue = data.tracks || [];
        this.renderQueueUI();
        this.loadAndPlaySong(data.startSong);
        return;
      } else if (data.tracks && data.tracks.length > 0) {
        const startSong = data.tracks[0];
        this.queue = data.tracks.slice(1);
        this.renderQueueUI();
        this.loadAndPlaySong(startSong);
        return;
      }
    } catch (e) {
      console.warn('雲端推薦接口請求失敗，採用藝人即時搜尋', e);
    }

    // 2. 備援搜尋該熱門藝人單曲（絕不將同歌手多首歌塞入佇列）
    const artist = this.getRandomArtist();
    this.searchAndPlay(artist);
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
    this.elVideoWrapper = document.getElementById('video-wrapper');
    this.elBtnToggleVideo = document.getElementById('btn-toggle-video');

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
    this.elBtnSleepMode = document.getElementById('btn-sleep-mode');
    this.elBlackoutScreen = document.getElementById('blackout-screen');
    this.elBlackoutSong = document.getElementById('blackout-song');
  }

  initEventListeners() {
    // 播放/暫停
    this.elBtnPlay.addEventListener('click', () => this.togglePlay());
    this.elBtnPrev.addEventListener('click', () => this.playPrev());
    this.elBtnNext.addEventListener('click', () => this.playNext());

    // 播放模式切換
    this.elBtnMode.addEventListener('click', () => this.toggleMode());

    // 切換 MV 畫面與純歌詞模式
    if (this.elBtnToggleVideo) {
      this.elBtnToggleVideo.addEventListener('click', () => {
        this.elVideoWrapper.classList.toggle('hidden');
        const isHidden = this.elVideoWrapper.classList.contains('hidden');
        this.elBtnToggleVideo.innerHTML = isHidden ? '<i class="fa-solid fa-film"></i>' : '<i class="fa-solid fa-align-left"></i>';
        this.showToast(isHidden ? '切換至：純歌詞大字模式' : '切換至：MV 影音畫面模式');
      });
    }

    // 進度條拖曳
    this.elProgressBar.addEventListener('input', (e) => {
      if (this.ytPlayer && typeof this.ytPlayer.getDuration === 'function') {
        const dur = this.ytPlayer.getDuration();
        if (dur > 0) {
          this.ytPlayer.seekTo((e.target.value / 100) * dur, true);
        }
      }
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
    document.getElementById('btn-queue-shuffle').addEventListener('click', () => this.regenerateRandomQueue());

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

    // iPhone 關螢幕教學彈窗
    const helpModal = document.getElementById('help-modal');
    const btnHelpOpen = document.getElementById('btn-help-open');
    const btnHelpClose = document.getElementById('btn-help-close');
    const btnHelpConfirm = document.getElementById('btn-help-confirm');

    if (btnHelpOpen && helpModal) {
      btnHelpOpen.addEventListener('click', () => helpModal.classList.remove('hidden'));
      if (btnHelpClose) btnHelpClose.addEventListener('click', () => helpModal.classList.add('hidden'));
      if (btnHelpConfirm) btnHelpConfirm.addEventListener('click', () => helpModal.classList.add('hidden'));
    }

    // 熄屏省電聽歌模式
    if (this.elBtnSleepMode && this.elBlackoutScreen) {
      this.elBtnSleepMode.addEventListener('click', () => this.enterSleepMode());
      this.elBlackoutScreen.addEventListener('click', () => this.exitSleepMode());
    }
  }

  async enterSleepMode() {
    this.elBlackoutScreen.classList.remove('hidden');
    if (this.currentSong) {
      this.elBlackoutSong.textContent = `${this.currentSong.title} - ${this.currentSong.artist}`;
    }
    this.showToast('已進入熄屏省電模式，點擊螢幕任意處可喚醒');
    try {
      if ('wakeLock' in navigator) {
        this.wakeLock = await navigator.wakeLock.request('screen');
      }
    } catch (e) {}
  }

  exitSleepMode() {
    this.elBlackoutScreen.classList.add('hidden');
    if (this.wakeLock) {
      this.wakeLock.release().catch(() => {});
      this.wakeLock = null;
    }
    this.showToast('已喚醒播放介面');
  }

  // ─── 🎬 YouTube 官方播放核心初始化 ───
  initYTPlayer() {
    this.ytPlayer = new YT.Player('yt-player', {
      height: '100%',
      width: '100%',
      playerVars: {
        'autoplay': 1,
        'playsinline': 1,
        'controls': 1,
        'rel': 0,
        'enablejsapi': 1
      },
      events: {
        'onReady': () => {
          this.isYTReady = true;
          try {
            const iframe = document.getElementById('yt-player');
            if (iframe && iframe.tagName === 'IFRAME') {
              iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
            }
          } catch (err) {}
          if (this.pendingSong) {
            this.loadAndPlaySong(this.pendingSong);
            this.pendingSong = null;
          }
        },
        'onStateChange': (e) => this.onYTStateChange(e),
        'onError': (e) => {
          console.warn('YouTube 播放器報錯 (代碼 ' + e.data + ')');
          if (!this.lastErrorTime || Date.now() - this.lastErrorTime > 3000) {
            this.lastErrorTime = Date.now();
            this.showToast('該版本播放受限，為您切換下一首');
          }
          clearTimeout(this.errorTimer);
          this.errorTimer = setTimeout(() => {
            this.playNext();
          }, 1500);
        }
      }
    });

    // 啟動即時同步定時器
    setInterval(() => this.onTimeUpdate(), 200);
  }

  onYTStateChange(e) {
    if (e.data === YT.PlayerState.PLAYING) {
      this.elBtnPlay.innerHTML = '<i class="fa-solid fa-pause"></i>';
      if ('mediaSession' in navigator) {
        navigator.mediaSession.playbackState = 'playing';
      }
      // 給予緩衝防抖，避免 iOS 剛起播數毫秒又暫停時過早結束切歌守護狀態
      clearTimeout(this.playingStabilizeTimer);
      this.playingStabilizeTimer = setTimeout(() => {
        if (this.ytPlayer && typeof this.ytPlayer.getPlayerState === 'function' && this.ytPlayer.getPlayerState() === YT.PlayerState.PLAYING) {
          this.isSwitchingTrack = false;
          clearInterval(this.autoPlayInterval);
        }
      }, 800);
    } else if (e.data === YT.PlayerState.PAUSED) {
      // 切歌過渡期：若剛載入新歌，YouTube 會先短暫觸發 PAUSED，此時強制自動起播！
      if (this.isSwitchingTrack) {
        if (this.ytPlayer && typeof this.ytPlayer.playVideo === 'function') {
          this.ytPlayer.playVideo();
        }
      } else {
        this.elBtnPlay.innerHTML = '<i class="fa-solid fa-play"></i>';
        if ('mediaSession' in navigator) {
          navigator.mediaSession.playbackState = 'paused';
        }
      }
    } else if (e.data === 5 /* CUED */ || e.data === -1 /* UNSTARTED */ || e.data === 3 /* BUFFERING */) {
      // 當新歌載入進入 CUED、BUFFERING 或 UNSTARTED，立即自動起播
      if (this.isSwitchingTrack) {
        if (this.ytPlayer && typeof this.ytPlayer.playVideo === 'function') {
          this.ytPlayer.playVideo();
        }
      }
    } else if (e.data === YT.PlayerState.ENDED) {
      if (this.mode === 'SINGLE') {
        this.ytPlayer.seekTo(0);
        this.ytPlayer.playVideo();
      } else {
        this.playNext();
      }
    }
  }

  // ─── 🎧 iOS 鎖定畫面與後台多媒體控制 ───
  initMediaSession() {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.setActionHandler('play', () => {
        if (this.ytPlayer && typeof this.ytPlayer.playVideo === 'function') {
          this.ytPlayer.playVideo();
        }
        navigator.mediaSession.playbackState = 'playing';
      });
      navigator.mediaSession.setActionHandler('pause', () => {
        this.isSwitchingTrack = false;
        clearInterval(this.autoPlayInterval);
        clearTimeout(this.switchTrackTimeout);
        clearTimeout(this.playingStabilizeTimer);
        if (this.ytPlayer && typeof this.ytPlayer.pauseVideo === 'function') {
          this.ytPlayer.pauseVideo();
        }
        navigator.mediaSession.playbackState = 'paused';
      });
      navigator.mediaSession.setActionHandler('previoustrack', () => this.playPrev());
      navigator.mediaSession.setActionHandler('nexttrack', () => this.playNext());
    }
  }

  updateMediaSession(title, artist) {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title,
        artist: artist,
        album: "Lynn's Cloud Music",
        artwork: [
          { src: 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=512&h=512&fit=crop', sizes: '512x512', type: 'image/jpeg' },
          { src: '/icon.ico', sizes: '128x128', type: 'image/x-icon' }
        ]
      });
      navigator.mediaSession.playbackState = 'playing';
    }
  }

  // ─── 🔍 搜尋與播放 ───
  async doSearch() {
    const q = this.elSearchInput.value.trim();
    if (!q) return;
    this.showToast('搜尋中...');
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&multi=1`);
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        this.renderSearchResults(data.results);
      } else if (data.song) {
        this.loadAndPlaySong(data.song);
      } else {
        this.showToast('找不到符合歌曲');
      }
    } catch (e) {
      this.showToast('搜尋失敗: ' + e.message);
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
      this.elSongTitle.textContent = `正在搜尋：${keyword}`;
      const res = await fetch(`/api/search?q=${encodeURIComponent(keyword)}`);
      const data = await res.json();
      if (data.song) {
        this.queue = [];
        this.renderQueueUI();
        this.loadAndPlaySong(data.song);
      }
    } catch (e) {
      this.showToast('搜尋失敗');
    }
  }

  loadAndPlaySong(song) {
    if (!this.isYTReady) {
      this.pendingSong = song;
      return;
    }

    this.isSwitchingTrack = true;
    this.elBtnPlay.innerHTML = '<i class="fa-solid fa-pause"></i>';
    clearTimeout(this.switchTrackTimeout);
    this.switchTrackTimeout = setTimeout(() => {
      this.isSwitchingTrack = false;
      clearInterval(this.autoPlayInterval);
    }, 4000);

    if (this.currentSong) {
      this.history.push(this.currentSong);
    }
    this.currentSong = song;
    this.playedIds.add(song.id);

    this.elSongTitle.textContent = song.title;
    this.elSongArtist.textContent = song.artist;
    this.updateFavButtonUI();
    this.updateMediaSession(song.title, song.artist);
    this.renderLyricsPlaceholder('正在載入動態歌詞與音樂...');

    // 1. 直接由手機原生調用 YouTube 官方播放 (免受機房封鎖)
    try {
      this.ytPlayer.loadVideoById(song.id, 0);
      this.ytPlayer.playVideo();

      // 強化自動起播輪詢迴圈：每 200ms 檢查一次，未播放則強制 playVideo，持續 3.6 秒
      clearInterval(this.autoPlayInterval);
      let attempts = 0;
      this.autoPlayInterval = setInterval(() => {
        attempts++;
        if (!this.ytPlayer || typeof this.ytPlayer.getPlayerState !== 'function') {
          if (attempts > 18) clearInterval(this.autoPlayInterval);
          return;
        }
        const state = this.ytPlayer.getPlayerState();
        if (state === YT.PlayerState.PLAYING) {
          if (attempts > 3) clearInterval(this.autoPlayInterval);
        } else {
          try {
            this.ytPlayer.playVideo();
          } catch (err) {}
          if (attempts > 18) {
            clearInterval(this.autoPlayInterval);
          }
        }
      }, 200);
    } catch (e) {
      console.warn('播放影片發生異常', e);
    }

    // 2. 平行非同步取得動態歌詞
    this.fetchLyrics(song.title, song.artist);

    // 3. 取得電台推薦 (若在 RADIO 模式且佇列即將用罄)
    if (this.mode === 'RADIO' && this.queue.length < 5) {
      this.fetchRadioQueue(song.id, song.artist, song.title);
    }
  }

  async fetchLyrics(title, artist) {
    try {
      const res = await fetch(`/api/lyrics?title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}`);
      const data = await res.json();
      if (data.lyrics && Object.keys(data.lyrics).length > 0) {
        this.parseLyrics(data.lyrics);
      } else {
        this.renderLyricsPlaceholder('(純音樂 / 暫無動態歌詞)');
      }
    } catch (e) {
      this.renderLyricsPlaceholder('(純音樂 / 暫無動態歌詞)');
    }
  }

  parseLyrics(rawLyrics) {
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

  async fetchRadioQueue(vid, artist = '', title = '') {
    try {
      const res = await fetch(`/api/radio?vid=${vid}&artist=${encodeURIComponent(artist)}&title=${encodeURIComponent(title)}`);
      const data = await res.json();
      if (data.tracks && data.tracks.length > 0) {
        const existingIds = new Set(this.queue.map(s => s.id));
        if (this.currentSong) existingIds.add(this.currentSong.id);

        // 嚴格藝人排重：即將播放清單絕不出現同一個藝人（包含正在播放的歌手）
        const existingArtists = new Set(this.queue.map(s => (s.artist || '').toLowerCase().trim()).filter(Boolean));
        if (this.currentSong && this.currentSong.artist) {
          existingArtists.add(this.currentSong.artist.toLowerCase().trim());
        }

        const newTracks = [];
        data.tracks.forEach(t => {
          const tArt = (t.artist || '').toLowerCase().trim();
          if (!this.playedIds.has(t.id) && !existingIds.has(t.id)) {
            // 若該歌手已在佇列中或正在播放，跳過以避免同歌手重複
            if (tArt && existingArtists.has(tArt)) {
              return;
            }
            newTracks.push(t);
            existingIds.add(t.id);
            if (tArt) existingArtists.add(tArt);
          }
        });
        if (newTracks.length > 0) {
          // 將最新取得的多樣化電台推薦依序加入佇列後端，保證歌手絕不重複
          this.queue = [...this.queue, ...newTracks];
          if (this.queue.length > 50) this.queue = this.queue.slice(0, 50);
          this.renderQueueUI();
        }
      }
    } catch (e) {
      console.log('取得電台失敗', e);
    }
  }

  // ─── ⏰ 播放更新與動態歌詞捲動 ───
  onTimeUpdate() {
    if (!this.ytPlayer || typeof this.ytPlayer.getCurrentTime !== 'function') return;

    const cur = this.ytPlayer.getCurrentTime() || 0;
    const dur = this.ytPlayer.getDuration() || 0;

    if (dur > 0) {
      const pct = (cur / dur) * 100;
      this.elProgressBar.value = pct;
      this.elCurrentTime.textContent = this.formatTime(cur);
      this.elTotalTime.textContent = this.formatTime(dur);
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

  togglePlay() {
    if (!this.ytPlayer || typeof this.ytPlayer.getPlayerState !== 'function') return;
    const state = this.ytPlayer.getPlayerState();
    if (state === YT.PlayerState.PLAYING) {
      this.isSwitchingTrack = false;
      clearInterval(this.autoPlayInterval);
      clearTimeout(this.switchTrackTimeout);
      clearTimeout(this.playingStabilizeTimer);
      this.ytPlayer.pauseVideo();
      if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    } else {
      this.isSwitchingTrack = false;
      this.ytPlayer.playVideo();
      if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
    }
  }

  playNext() {
    if (this.mode === 'LOOP' && this.currentSong) {
      this.queue.push(this.currentSong);
    }

    if (this.queue.length > 0) {
      const next = this.queue.shift();
      this.renderQueueUI();
      this.loadAndPlaySong(next);

      // 當佇列剩餘不到 4 首時，提前在背景向雲端補充新電台，保證歌單永不間斷
      if (this.queue.length < 4 && this.mode === 'RADIO') {
        this.fetchRadioQueue(next.id, next.artist, next.title);
      }
    } else {
      // 萬一佇列空了，隨機由熱門藝人補上推薦歌曲
      this.initRandomPopularArtist();
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
      this.elBtnMode.innerHTML = '<i class="fa-solid fa-rotate-right"></i> 單曲循環';
      this.showToast('模式：單曲循環');
    } else if (this.mode === 'SINGLE') {
      this.mode = 'LOOP';
      this.elBtnMode.innerHTML = '<i class="fa-solid fa-repeat"></i> 佇列循環';
      this.showToast('模式：佇列循環');
    } else {
      this.mode = 'RADIO';
      this.elBtnMode.innerHTML = '<i class="fa-solid fa-shuffle"></i> 隨機電台';
      this.showToast('模式：隨機電台');
    }
  }

  formatTime(secs) {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  // ─── 我的最愛 (localStorage: lynn_favorites) ───
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
      this.showToast('已從我的最愛移除');
    } else {
      this.favorites.push({ ...this.currentSong });
      this.showToast('已加入我的最愛');
    }
    this.saveFavorites();
  }

  updateFavButtonUI() {
    if (!this.currentSong) {
      this.elFavToggle.innerHTML = '<i class="fa-regular fa-heart"></i>';
      return;
    }
    const isFav = this.isFavorite(this.currentSong.id);
    this.elFavToggle.innerHTML = isFav
      ? '<i class="fa-solid fa-heart"></i>'
      : '<i class="fa-regular fa-heart"></i>';
  }

  openFavDrawer() {
    this.elFavList.innerHTML = '';
    this.elFavCount.textContent = this.favorites.length;
    if (this.favorites.length === 0) {
      this.elFavList.innerHTML = '<p class="empty-hint">尚無收藏歌曲，聽歌時點擊愛心即可收藏</p>';
    } else {
      this.favorites.forEach((song, idx) => {
        const item = document.createElement('div');
        const isPlayingThis = this.currentSong && this.currentSong.id === song.id;
        item.className = `list-item ${isPlayingThis ? 'active-playing' : ''}`;
        item.innerHTML = `
          <button class="item-play-btn" title="播放這首歌曲"><i class="fa-solid fa-play"></i></button>
          <div class="list-item-info">
            <div class="list-item-title">${idx + 1}. ${song.title}</div>
            <div class="list-item-artist">${song.artist}</div>
          </div>
          <button class="list-item-del" title="移除收藏"><i class="fa-regular fa-trash-can"></i></button>
        `;

        const playFavSong = () => {
          const subsequent = this.favorites.slice(idx + 1);
          const preceding = this.favorites.slice(0, idx);
          this.queue = [...subsequent, ...preceding];
          this.renderQueueUI();
          this.elFavDrawer.classList.add('hidden');
          this.loadAndPlaySong(song);
          this.showToast(`播放：${song.title}`);
        };

        item.querySelector('.item-play-btn').addEventListener('click', (e) => {
          e.stopPropagation();
          playFavSong();
        });

        item.querySelector('.list-item-info').addEventListener('click', () => {
          playFavSong();
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

  // ─── 自訂歌單 (localStorage: lynn_custom_playlists) ───
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
      this.showToast('目前沒有正在播放的歌曲');
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
      this.elModalPlaylistOptions.innerHTML = '<p class="empty-hint" style="padding: 10px;">尚未建立任何自訂歌單</p>';
      return;
    }
    playlistNames.forEach(name => {
      const btn = document.createElement('button');
      btn.className = 'modal-pl-btn';
      const count = this.customPlaylists[name].length;
      btn.innerHTML = `<span><i class="fa-regular fa-folder" style="color: var(--accent); margin-right: 8px;"></i>${name}</span><span style="font-size:12px; color: var(--accent);">(${count} 首)</span>`;
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
      this.showToast('請輸入歌單名稱');
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
      this.showToast(`歌曲已在「${playlistName}」中`);
      return;
    }
    list.push({ ...song });
    this.saveCustomPlaylists();
    this.showToast(`已加入「${playlistName}」`);
  }

  openPlaylistsDrawer() {
    this.renderPlaylistsDrawer();
    this.elPlaylistsDrawer.classList.remove('hidden');
  }

  renderPlaylistsDrawer() {
    this.elPlaylistsList.innerHTML = '';
    const playlistNames = Object.keys(this.customPlaylists);
    if (playlistNames.length === 0) {
      this.elPlaylistsList.innerHTML = '<p class="empty-hint">尚無自訂歌單，點擊「+」按鈕即可新增！</p>';
      return;
    }

    playlistNames.forEach(name => {
      const songs = this.customPlaylists[name];
      const card = document.createElement('div');
      card.className = 'playlist-card';

      card.innerHTML = `
        <div class="playlist-card-header">
          <div class="playlist-card-title-group">
            <i class="fa-regular fa-folder" style="color: var(--accent);"></i>
            <span class="playlist-card-title">${name}</span>
            <span class="playlist-card-count">${songs.length} 首</span>
          </div>
          <div class="playlist-card-actions">
            <button class="btn-sm btn-play-pl" title="播放整張歌單"><i class="fa-solid fa-play"></i> 播放整張</button>
            <button class="btn-sm btn-del-pl" title="刪除整張歌單"><i class="fa-regular fa-trash-can"></i></button>
          </div>
        </div>
        <div class="playlist-songs-list"></div>
      `;

      const header = card.querySelector('.playlist-card-header');
      const songsList = card.querySelector('.playlist-songs-list');
      const btnPlayAll = card.querySelector('.btn-play-pl');
      const btnDelPl = card.querySelector('.btn-del-pl');

      // 點擊標題群組展開/收合
      header.querySelector('.playlist-card-title-group').addEventListener('click', () => {
        songsList.classList.toggle('hidden');
      });

      // 播放整張歌單
      btnPlayAll.addEventListener('click', (e) => {
        e.stopPropagation();
        if (songs.length === 0) {
          this.showToast('歌單內目前沒有歌曲');
          return;
        }
        this.queue = [...songs.slice(1)];
        this.renderQueueUI();
        this.elPlaylistsDrawer.classList.add('hidden');
        this.loadAndPlaySong(songs[0]);
        this.showToast(`正在播放歌單「${name}」`);
      });

      // 刪除整張歌單
      btnDelPl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm(`確定要刪除整個歌單「${name}」嗎？`)) {
          delete this.customPlaylists[name];
          this.saveCustomPlaylists();
          this.renderPlaylistsDrawer();
          this.showToast(`已刪除歌單「${name}」`);
        }
      });

      // 渲染歌單內的每一首歌，提供自由點選播放功能
      if (songs.length === 0) {
        songsList.innerHTML = '<p class="empty-hint" style="padding: 10px;">(空歌單)</p>';
      } else {
        songs.forEach((s, sIdx) => {
          const sItem = document.createElement('div');
          const isPlayingThis = this.currentSong && this.currentSong.id === s.id;
          sItem.className = `list-item ${isPlayingThis ? 'active-playing' : ''}`;
          sItem.innerHTML = `
            <button class="item-play-btn" title="播放這首歌曲"><i class="fa-solid fa-play"></i></button>
            <div class="list-item-info">
              <div class="list-item-title">${sIdx + 1}. ${s.title}</div>
              <div class="list-item-artist">${s.artist}</div>
            </div>
            <button class="list-item-del" title="移出歌單"><i class="fa-solid fa-xmark"></i></button>
          `;

          // 核心功能：自訂歌單點選播放哪一首歌，並自動將該歌單後續歌曲排入即將播放清單
          const playThisPlaylistSong = () => {
            const subsequent = songs.slice(sIdx + 1);
            const preceding = songs.slice(0, sIdx);
            this.queue = [...subsequent, ...preceding];
            this.renderQueueUI();
            this.elPlaylistsDrawer.classList.add('hidden');
            this.loadAndPlaySong(s);
            this.showToast(`播放：${s.title}`);
          };

          sItem.querySelector('.item-play-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            playThisPlaylistSong();
          });

          sItem.querySelector('.list-item-info').addEventListener('click', () => {
            playThisPlaylistSong();
          });

          sItem.querySelector('.list-item-del').addEventListener('click', (ev) => {
            ev.stopPropagation();
            songs.splice(sIdx, 1);
            this.saveCustomPlaylists();
            this.renderPlaylistsDrawer();
            this.showToast(`已從歌單移出：${s.title}`);
          });

          songsList.appendChild(sItem);
        });
      }

      this.elPlaylistsList.appendChild(card);
    });
  }

  // ─── 即將播放佇列 ───
  openQueueDrawer() {
    this.renderQueueUI();
    this.elQueueDrawer.classList.remove('hidden');
  }

  renderQueueUI() {
    const btnQueue = document.getElementById('btn-queue-open');
    if (btnQueue) {
      btnQueue.innerHTML = this.queue.length > 0
        ? `<i class="fa-solid fa-list-ul"></i><span class="badge-counter">${this.queue.length}</span>`
        : '<i class="fa-solid fa-list-ul"></i>';
    }

    this.elQueueList.innerHTML = '';
    if (this.queue.length === 0) {
      this.elQueueList.innerHTML = '<p class="empty-hint">佇列目前為空</p>';
      return;
    }
    this.queue.forEach((song, idx) => {
      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <button class="item-play-btn" title="立即播放此首"><i class="fa-solid fa-play"></i></button>
        <div class="list-item-info">
          <div class="list-item-title">${idx + 1}. ${song.title}</div>
          <div class="list-item-artist">${song.artist}</div>
        </div>
        <button class="list-item-del" title="移出佇列"><i class="fa-solid fa-xmark"></i></button>
      `;

      const playQueueSong = () => {
        this.elQueueDrawer.classList.add('hidden');
        this.queue.splice(idx, 1);
        this.loadAndPlaySong(song);
      };

      item.querySelector('.item-play-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        playQueueSong();
      });

      item.querySelector('.list-item-info').addEventListener('click', () => {
        playQueueSong();
      });

      item.querySelector('.list-item-del').addEventListener('click', (e) => {
        e.stopPropagation();
        this.queue.splice(idx, 1);
        this.renderQueueUI();
      });

      this.elQueueList.appendChild(item);
    });
  }

  async regenerateRandomQueue() {
    this.showToast('正在隨機生成全新多元歌手歌單...');
    try {
      const curArt = this.currentSong ? this.currentSong.artist : '';
      const queueArtists = this.queue.map(s => s.artist).filter(Boolean);
      const res = await fetch(`/api/random_queue?exclude=${encodeURIComponent(curArt)}&exclude_artists=${encodeURIComponent(queueArtists.join(','))}&t=${Date.now()}`);
      const data = await res.json();
      if (data.tracks && data.tracks.length > 0) {
        this.queue = data.tracks;
        this.renderQueueUI();
        this.showToast(`已生成 ${data.tracks.length} 首完全不同歌手的全新電台！`);
        return;
      }
    } catch (e) {
      console.warn('雲端隨機歌單失敗，使用本機打亂', e);
    }
    this.shuffleQueue();
  }

  shuffleQueue() {
    for (let i = this.queue.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [this.queue[i], this.queue[j]] = [this.queue[j], this.queue[i]];
    }
    // 隨機後若有連續相同歌手，智慧錯開
    for (let i = 0; i < this.queue.length - 1; i++) {
      if (this.queue[i].artist && this.queue[i].artist === this.queue[i+1].artist) {
        for (let j = i + 2; j < this.queue.length; j++) {
          if (this.queue[j].artist !== this.queue[i].artist) {
            [this.queue[i+1], this.queue[j]] = [this.queue[j], this.queue[i+1]];
            break;
          }
        }
      }
    }
    this.renderQueueUI();
    this.showToast('佇列已打亂');
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

// ─── 全域啟動 ───
window.player = null;
window.isYTAPIReady = false;

window.onYouTubeIframeAPIReady = function() {
  window.isYTAPIReady = true;
  if (window.player && !window.player.ytPlayer) {
    window.player.initYTPlayer();
  }
};

window.addEventListener('DOMContentLoaded', () => {
  window.player = new LynnMobilePlayer();
  if (window.isYTAPIReady || (window.YT && window.YT.Player)) {
    window.player.initYTPlayer();
  }
});
