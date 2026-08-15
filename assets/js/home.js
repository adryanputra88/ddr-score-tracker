/* ==========================================================================
   Home dashboard: overview totals, level distribution, precision spread,
   hall of fame. All numbers animate on load / refresh.
   ========================================================================== */

(function () {
  'use strict';

  var DDR = window.DDR;
  var DATA = window.DDR_DATA;
  if (!DATA) return;

  var records = DATA.records;
  var $ = DDR.$;

  /* ------------------------------------------------------------- summarise */

  var scored = records.filter(function (r) { return typeof r.perfects === 'number'; });
  var levelled = records.filter(function (r) { return r.level; });

  var summary = {
    total: records.length,
    pfc: records.length,               // every logged row is a Perfect Full Combo
    esp: records.filter(function (r) { return r.difficulty === 'ESP'; }).length,
    csp: records.filter(function (r) { return r.difficulty === 'CSP'; }).length,
    sdp: scored.filter(function (r) { return r.perfects < 10; }).length,
    mfc: scored.filter(function (r) { return r.perfects === 0; }).length,
    maxLevel: levelled.length ? Math.max.apply(null, levelled.map(function (r) { return r.level; })) : null,
    best: scored.length ? Math.max.apply(null, scored.map(function (r) { return r.score; })) : null,
    unlogged: records.length - scored.length
  };

  var bestRecord = scored.filter(function (r) { return r.score === summary.best; })[0];
  var peakRecord = levelled.filter(function (r) { return r.level === summary.maxLevel; })
    .sort(function (a, b) { return (a.perfects || 999) - (b.perfects || 999); })[0];

  /* ---------------------------------------------------------- hero metrics */

  function setMetric(id, value, note) {
    $('#' + id).dataset.count = value;
    var noteEl = $('#' + id + '-note');
    if (!noteEl) return;
    if (note) noteEl.textContent = note;
    else noteEl.remove();
  }

  setMetric('m-pfc', summary.pfc, null);
  setMetric('m-sdp', summary.sdp,
    summary.mfc ? summary.mfc + ' of them Marvelous' : 'Under 10 Perfects');
  setMetric('m-best', summary.best, bestRecord ? bestRecord.title : null);

  // Expert and Challenge get their own capsule in the difficulty colours the
  // records page uses, rather than one run-on line.
  $('#m-pfc-split').innerHTML =
    '<span class="capsule capsule--esp"><strong>' + summary.esp + '</strong> Expert</span>' +
    '<span class="capsule capsule--csp"><strong>' + summary.csp + '</strong> Challenge</span>';

  /* ------------------------------------------------------- latest clear */

  // The workbook is sorted alphabetically and carries no dates, so the most
  // recent clear cannot be derived from it — it is named in tools/site.json.
  var latest = (DATA.site && DATA.site.latestRecord || '').trim();
  if (latest) {
    $('#latest-song').textContent = latest;
    $('#latest-wrap').hidden = false;
  }

  /* --------------------------------------------------------- title SFX */

  (function initSfx() {
    var btn = $('#sfx-title');
    var audio = $('#sfx-audio');
    if (!btn || !audio) return;

    // Tooltip rides the pointer, sitting just above it.
    var tip = document.createElement('div');
    tip.className = 'cursor-tip';
    tip.textContent = btn.dataset.tip;
    document.body.appendChild(tip);

    btn.addEventListener('pointerenter', function () { tip.classList.add('is-on'); });
    btn.addEventListener('pointerleave', function () { tip.classList.remove('is-on'); });
    btn.addEventListener('pointermove', function (e) {
      tip.style.left = e.clientX + 'px';
      tip.style.top = (e.clientY - 18) + 'px';
    });

    btn.addEventListener('click', function () {
      audio.currentTime = 0;
      var played = audio.play();
      if (played && played.catch) played.catch(function () {});
      btn.classList.add('is-playing');
    });
    audio.addEventListener('ended', function () {
      btn.classList.remove('is-playing');
    });
  }());

  /* ------------------------------------------------------------------ rail */

  var railItems = [
    {
      value: summary.maxLevel ? 'Lv.' + summary.maxLevel : '—',
      label: 'Highest level PFC’d' + (peakRecord ? ' · ' + peakRecord.title : ''),
      lead: true
    },
    { value: summary.total, label: 'Songs recorded', count: true },
    { value: summary.esp, label: 'Expert Single Play', count: true },
    { value: summary.csp, label: 'Challenge Single Play', count: true },
    {
      value: levelled.length,
      label: 'Charts with a rated level',
      count: true
    },
    { value: DATA.sourceUpdated, label: 'Last updated' }
  ];

  $('#rail').innerHTML = railItems.map(function (item) {
    var value = item.count
      ? '<span class="rail__value" data-count="' + item.value + '">0</span>'
      : '<span class="rail__value">' + item.value + '</span>';
    return '<div class="rail__item">' +
      value + '<span class="rail__label">' + item.label + '</span></div>';
  }).join('');


  /* ------------------------------------------------------- level bar chart */

  /** Grow the bars and circles to their final size, guaranteeing the end state. */
  function growBars() {
    DDR.settle(
      DDR.$$('.bar-row__fill'),
      { width: function (el) { return el.dataset.width + '%'; } },
      1600
    );
    DDR.settle(
      DDR.$$('.circle-cell__inner'),
      {
        width: function (el) { return el.dataset.size + '%'; },
        height: function (el) { return el.dataset.size + '%'; }
      },
      1500
    );
  }

  var barsMode = 'level';

  function buildLevelBars() {
    var byLevel = {};
    levelled.forEach(function (r) { byLevel[r.level] = (byLevel[r.level] || 0) + 1; });

    var rows = Object.keys(byLevel).map(function (lv) {
      return { level: Number(lv), key: 'Lv.' + lv, count: byLevel[lv] };
    });

    var unrated = records.length - levelled.length;
    // Unrated has no level, so it always tails the list whichever sort is on.
    if (unrated) rows.push({ level: -1, key: 'Unrated', count: unrated, dim: true });

    rows.sort(function (a, b) {
      if (a.dim || b.dim) return (a.dim ? 1 : 0) - (b.dim ? 1 : 0);
      return barsMode === 'count'
        ? b.count - a.count || b.level - a.level
        : b.level - a.level;
    });

    var max = Math.max.apply(null, rows.map(function (r) { return r.count; }));

    $('#level-bars').innerHTML = rows.map(function (r) {
      var share = ((r.count / records.length) * 100).toFixed(1);
      return '' +
        '<div class="bar-row">' +
          '<span class="bar-row__key">' + r.key + '</span>' +
          '<span class="bar-row__track">' +
            '<span class="bar-row__fill"' +
              ' data-width="' + ((r.count / max) * 100) + '"' +
              (r.dim ? ' style="filter:grayscale(1);opacity:.45"' : '') + '>' +
              '<span>' + r.count + '</span>' +
            '</span>' +
          '</span>' +
          '<span class="bar-row__meta">' + share + '%</span>' +
        '</div>';
    }).join('');
  }

  buildLevelBars();

  DDR.$$('.seg [data-bars]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (barsMode === btn.dataset.bars) return;
      barsMode = btn.dataset.bars;
      DDR.$$('.seg [data-bars]').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      buildLevelBars();
      growBars();
    });
  });

  /* ----------------------------------------------------- precision circles */

  (function buildPrecision() {
    var buckets = [
      { label: '0–4 P', test: function (p) { return p <= 4; } },
      { label: '5–9 P', test: function (p) { return p >= 5 && p <= 9; } },
      { label: '10–19 P', test: function (p) { return p >= 10 && p <= 19; } },
      { label: '20–29 P', test: function (p) { return p >= 20 && p <= 29; } },
      { label: '30–39 P', test: function (p) { return p >= 30 && p <= 39; } },
      { label: '40+ P', test: function (p) { return p >= 40; } }
    ];

    var counts = buckets.map(function (b) {
      return scored.filter(function (r) { return b.test(r.perfects); }).length;
    });
    var max = Math.max.apply(null, counts) || 1;

    $('#precision').innerHTML = buckets.map(function (b, i) {
      var share = ((counts[i] / scored.length) * 100).toFixed(1);
      // Area-proportional: radius scales with the square root of the share.
      var size = Math.sqrt(counts[i] / max) * 100;
      return '' +
        '<div class="circle-cell">' +
          '<div class="circle-cell__disc">' +
            '<div class="circle-cell__inner" data-size="' + size.toFixed(1) + '"></div>' +
          '</div>' +
          '<div class="circle-cell__label">' + b.label + '</div>' +
          '<div class="circle-cell__value">' + share + '%</div>' +
        '</div>';
    }).join('');
  }());

  /* -------------------------------------------------------- hall of fame */

  (function buildHof() {
    var top = scored.slice().sort(function (a, b) {
      if (a.perfects !== b.perfects) return a.perfects - b.perfects;
      return (b.level || 0) - (a.level || 0);
    }).slice(0, 15);

    $('#hof').innerHTML = top.map(function (r) {
      var bits = ['<b>' + r.perfects + 'P</b>', '<b>' + DDR.num(r.score) + '</b>'];
      if (r.level) bits.splice(1, 0, 'Lv.' + r.level);
      return '' +
        '<button class="hof__card" type="button" data-id="' +
            DDR.esc(r.source) + '|' + r.difficulty + '">' +
          DDR.jacketHtml(r, 'hof__jacket') +
          '<span class="hof__body">' +
            '<span class="hof__title" title="' + DDR.esc(r.title) + '">' + DDR.esc(r.title) + '</span>' +
            '<span class="hof__meta">' + bits.join(' · ') + '</span>' +
          '</span>' +
        '</button>';
    }).join('');

    // Same detail panel the archive uses.
    $('#hof').addEventListener('click', function (e) {
      var card = e.target.closest('.hof__card');
      if (!card) return;
      var parts = card.dataset.id.split('|');
      var record = records.filter(function (r) {
        return r.source === parts[0] && r.difficulty === parts[1];
      })[0];
      if (record) DDR.openDrawer(record);
    });
  }());

  /* --------------------------------------------------------------- animate */

  function play() {
    DDR.runCounters();
    if (DDR.reducedMotion) growBars();
    else setTimeout(growBars, 220);
  }

  // Re-run when the page is restored from the back/forward cache too, so a
  // "refresh" always replays the animation.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', play);
  } else {
    play();
  }
  window.addEventListener('pageshow', function (e) { if (e.persisted) play(); });
}());
