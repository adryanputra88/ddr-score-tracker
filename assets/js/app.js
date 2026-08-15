/* ==========================================================================
   Shared shell: theme, mobile nav, background music, number animation.
   Loaded on every page before the per-page script.
   ========================================================================== */

(function () {
  'use strict';

  /* ---------------------------------------------------------------- config */

  // Selectable background mixes, one per DDR release. Add or reorder freely —
  // the picker in the player bar is built from this list.
  // `palette` keys a background colour scheme in style.css, so picking a mix
  // also re-skins the page to that release's artwork.
  var MIXES = [
    { id: 'raPf7_u5wws', name: 'DDR EXTREME',    palette: 'ddr-extreme' },
    { id: 'n-_IcbEY6jM', name: 'DDR SuperNOVA2', palette: 'ddr-supernova2' },
    { id: '9JwlJqTi65A', name: 'DDR X',          palette: 'ddr-x' },
    { id: 'hLLNZ7s5DkA', name: 'DDR X2',         palette: 'ddr-x2' },
    { id: 'KcdMwgN_BX0', name: 'DDR 2013',       palette: 'ddr-2013' },
    { id: 'DHV1mG-BDlg', name: 'DDR A',          palette: 'ddr-a' },
    { id: 'lmqqLv3lwjE', name: 'DDR A20',        palette: 'ddr-a20' },
    { id: 'eavCDuhTkv0', name: 'DDR WORLD',      palette: 'ddr-world' }
  ];
  var DEFAULT_MIX = 'KcdMwgN_BX0';   // DDR 2013

  var STORE = {
    theme: 'ddr.theme',
    volume: 'ddr.volume',
    muted: 'ddr.muted',
    mix: 'ddr.mix',
    palette: 'ddr.palette'
  };

  /* ----------------------------------------------------------------- utils */

  var DDR = window.DDR || (window.DDR = {});

  DDR.$ = function (sel, root) { return (root || document).querySelector(sel); };
  DDR.$$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  DDR.num = function (n) {
    return typeof n === 'number' ? n.toLocaleString('en-US') : '--';
  };

  DDR.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function store(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* private mode */ }
    return null;
  }
  DDR.store = store;

  /* ----------------------------------------------------------------- theme */

  // The initial theme is set by an inline snippet in <head> so there is no
  // flash; this only wires up the toggle.
  function initTheme() {
    var btn = DDR.$('.theme-toggle');
    if (!btn) return;

    function reflect() {
      var light = document.documentElement.dataset.theme === 'light';
      btn.setAttribute('aria-checked', String(light));
      btn.setAttribute('aria-label',
        'Switch to ' + (light ? 'dark' : 'light') + ' theme');
    }
    reflect();

    btn.addEventListener('click', function () {
      document.documentElement.dataset.theme =
        document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
      reflect();
      store(STORE.theme, document.documentElement.dataset.theme);
    });
  }

  /* ------------------------------------------------------------------- nav */

  function initNav() {
    var toggle = DDR.$('.nav-toggle');
    var nav = DDR.$('.nav');
    if (!toggle || !nav) return;
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* --------------------------------------------------------- number ticker */

  /**
   * Count an element up to `to` on load. Elements opt in with
   * data-count="<number>" plus an optional data-count-prefix / -suffix.
   */
  DDR.countUp = function (el, to, opts) {
    opts = opts || {};
    var prefix = opts.prefix || '';
    var suffix = opts.suffix || '';
    var duration = opts.duration || 1400;

    function paint(v) {
      el.textContent = prefix + Math.round(v).toLocaleString('en-US') + suffix;
    }

    if (DDR.reducedMotion || !to) { paint(to || 0); return; }

    var done = false;
    var startedAt = null;
    function frame(now) {
      if (done) return;
      if (startedAt === null) startedAt = now;
      var t = Math.min(1, (now - startedAt) / duration);
      // easeOutExpo — fast out of the gate, long settle.
      var eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      paint(to * eased);
      if (t < 1) requestAnimationFrame(frame);
      else done = true;
    }
    paint(0);
    requestAnimationFrame(frame);

    // requestAnimationFrame is paused while the tab is hidden, which would
    // otherwise leave the number frozen at 0 for anyone who opens the page in a
    // background tab. Land on the real value regardless.
    setTimeout(function () {
      if (!done) { done = true; paint(to); }
    }, duration + 400);
  };

  /**
   * Apply `props` to `els` with their CSS transition, then guarantee the end
   * state. A transition started while the tab is hidden or throttled can stall
   * part-way and never resume, which would leave a chart frozen mid-grow; the
   * timeout drops the transition and pins the final values.
   */
  DDR.settle = function (els, props, duration) {
    els.forEach(function (el) {
      Object.keys(props).forEach(function (prop) {
        el.style[prop] = props[prop](el);
      });
    });
    setTimeout(function () {
      els.forEach(function (el) {
        el.style.transition = 'none';
        Object.keys(props).forEach(function (prop) {
          el.style[prop] = props[prop](el);
        });
      });
    }, duration);
  };

  /** Run every [data-count] in `root`, staggered slightly. */
  DDR.runCounters = function (root) {
    DDR.$$('[data-count]', root || document).forEach(function (el, i) {
      var to = parseFloat(el.dataset.count);
      var run = function () {
        DDR.countUp(el, to, {
          prefix: el.dataset.countPrefix || '',
          suffix: el.dataset.countSuffix || '',
          duration: 1100 + (i % 4) * 180
        });
      };
      if (DDR.reducedMotion) run();
      else setTimeout(run, 90 + i * 70);
    });
  };

  /* ---------------------------------------------------------------- player */

  /**
   * Background audio via the YouTube IFrame API.
   *
   * Browsers only allow unattended playback when it is muted, so the player
   * starts muted and the bar shows an "enable sound" affordance. Once the
   * listener opts in, the choice and volume are remembered across pages.
   */
  function initPlayer() {
    var bar = DDR.$('.player');
    if (!bar) return;

    var host = DDR.$('#yt-host');
    var playBtn = DDR.$('.player__btn--play', bar);
    var muteBtn = DDR.$('.player__btn--mute', bar);
    var volume = DDR.$('.player__volume', bar);
    var hint = DDR.$('.player__hint', bar);
    var picker = DDR.$('.player__select', bar);
    var player = null;
    var ready = false;

    var wantsSound = store(STORE.muted) === 'false';
    var savedVolume = parseInt(store(STORE.volume) || '35', 10);
    volume.value = savedVolume;

    var saved = store(STORE.mix);
    var currentMix = MIXES.filter(function (m) { return m.id === saved; })[0]
      || MIXES.filter(function (m) { return m.id === DEFAULT_MIX; })[0]
      || MIXES[0];

    picker.innerHTML = MIXES.map(function (m) {
      return '<option value="' + m.id + '"' +
        (m.id === currentMix.id ? ' selected' : '') + '>' + m.name + '</option>';
    }).join('');

    // The gradient itself can't be transitioned, so the whole layer fades out,
    // swaps palette, and fades back in.
    var glow = DDR.$('.glow');
    function applyPalette(mix, animate) {
      // Remembered so the inline <head> script can set it before first paint.
      store(STORE.palette, mix.palette);
      if (!animate || !glow || DDR.reducedMotion) {
        document.documentElement.dataset.mix = mix.palette;
        return;
      }
      glow.style.opacity = '0';
      setTimeout(function () {
        document.documentElement.dataset.mix = mix.palette;
        glow.style.opacity = '';
      }, 340);
    }
    applyPalette(currentMix, false);

    function reflect(playing) {
      bar.classList.toggle('is-playing', playing);
      playBtn.classList.toggle('is-playing', playing);
      playBtn.setAttribute('aria-label', playing ? 'Pause music' : 'Play music');
    }

    function reflectMute(muted) {
      muteBtn.classList.toggle('is-muted', muted);
      muteBtn.setAttribute('aria-label', muted ? 'Unmute' : 'Mute');
      hint.hidden = !muted;
    }

    window.onYouTubeIframeAPIReady = function () {
      player = new window.YT.Player(host, {
        videoId: currentMix.id,
        playerVars: {
          autoplay: 1,
          controls: 0,
          disablekb: 1,
          modestbranding: 1,
          playsinline: 1,
          rel: 0
        },
        events: {
          onReady: function (e) {
            ready = true;
            e.target.setVolume(savedVolume);
            if (wantsSound) { e.target.unMute(); } else { e.target.mute(); }
            reflectMute(!wantsSound);
            e.target.playVideo();
          },
          onStateChange: function (e) {
            reflect(e.data === window.YT.PlayerState.PLAYING);
            // These uploads are long mixes; loop rather than let one stop.
            if (e.data === window.YT.PlayerState.ENDED) e.target.seekTo(0);
          },
          onError: function () {
            picker.disabled = true;
            DDR.$('.player__label', bar).textContent = 'Music unavailable';
            hint.hidden = true;
          }
        }
      });
    };

    picker.addEventListener('change', function () {
      var next = MIXES.filter(function (m) { return m.id === picker.value; })[0];
      if (!next) return;
      currentMix = next;
      store(STORE.mix, next.id);
      applyPalette(next, true);
      if (!ready) return;
      // loadVideoById starts playback, which is only allowed unattended while
      // muted — so a listener who hasn't opted into sound stays muted.
      player.loadVideoById(next.id);
      player.setVolume(parseInt(volume.value, 10));
      if (muteBtn.classList.contains('is-muted')) player.mute();
    });

    playBtn.addEventListener('click', function () {
      if (!ready) return;
      if (bar.classList.contains('is-playing')) player.pauseVideo();
      else player.playVideo();
    });

    function enableSound() {
      if (!ready) return;
      player.unMute();
      player.setVolume(parseInt(volume.value, 10));
      player.playVideo();
      reflectMute(false);
      store(STORE.muted, 'false');
    }

    muteBtn.addEventListener('click', function () {
      if (!ready) return;
      if (muteBtn.classList.contains('is-muted')) {
        enableSound();
      } else {
        player.mute();
        reflectMute(true);
        store(STORE.muted, 'true');
      }
    });

    hint.addEventListener('click', enableSound);

    volume.addEventListener('input', function () {
      var v = parseInt(volume.value, 10);
      store(STORE.volume, String(v));
      if (!ready) return;
      player.setVolume(v);
      if (v > 0 && muteBtn.classList.contains('is-muted')) enableSound();
    });

    var tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(tag);
  }

  /* ------------------------------------------------------------------ boot */

  function boot() {
    initTheme();
    initNav();
    initPlayer();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
