/* ==========================================================================
   My Records: filter / sort the archive and open a detail drawer per chart.
   ========================================================================== */

(function () {
  'use strict';

  var DDR = window.DDR;
  var DATA = window.DDR_DATA;
  if (!DATA) return;

  var $ = DDR.$;
  var $$ = DDR.$$;
  var records = DATA.records;

  var grid = $('#grid');
  var empty = $('#empty');

  var state = { q: '', diff: '', level: '', origin: '', sort: 'alpha' };

  /* ---------------------------------------------------------------- helpers */

  // Sort key that ignores case, punctuation and leading symbols so "↑↑↓↓" and
  // "#OurMemories" land somewhere sensible rather than all bunched at the top.
  function sortKey(r) {
    return (r.title || '').toLowerCase()
      .replace(/[^a-z0-9぀-ヿ一-鿿]+/g, '');
  }


  /* --------------------------------------------------------- filter options */

  (function fillOptions() {
    var levels = records
      .map(function (r) { return r.level; })
      .filter(Boolean)
      .filter(function (v, i, a) { return a.indexOf(v) === i; })
      .sort(function (a, b) { return b - a; });

    $('#level').insertAdjacentHTML('beforeend', levels.map(function (lv) {
      return '<option value="' + lv + '">Lv.' + lv + '</option>';
    }).join('') + '<option value="none">Unrated</option>');

    var seen = {};
    records.forEach(function (r) {
      if (r.origin) seen[r.origin] = r.originOrder;
    });
    var origins = Object.keys(seen).sort(function (a, b) {
      return (seen[a] - seen[b]) || a.localeCompare(b);
    });

    $('#origin').insertAdjacentHTML('beforeend', origins.map(function (o) {
      return '<option value="' + DDR.esc(o) + '">' + DDR.esc(o) + '</option>';
    }).join(''));
  }());

  /* ------------------------------------------------------------- filtering */

  function apply() {
    var q = state.q.trim().toLowerCase();

    var rows = records.filter(function (r) {
      if (state.diff && r.difficulty !== state.diff) return false;
      if (state.level === 'none' && r.level) return false;
      if (state.level && state.level !== 'none' && String(r.level) !== state.level) return false;
      if (state.origin && r.origin !== state.origin) return false;
      if (q) {
        var hay = [r.title, r.titleAlt, r.source, r.artist].join(' ').toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });

    var by = {
      alpha: function (a, b) { return sortKey(a).localeCompare(sortKey(b)); },
      'alpha-desc': function (a, b) { return sortKey(b).localeCompare(sortKey(a)); },
      'score-desc': function (a, b) { return (b.score || -1) - (a.score || -1); },
      'score-asc': function (a, b) { return (a.score === null ? Infinity : a.score) - (b.score === null ? Infinity : b.score); },
      'level-desc': function (a, b) { return (b.level || 0) - (a.level || 0); },
      'level-asc': function (a, b) { return (a.level || 99) - (b.level || 99); },
      difficulty: function (a, b) { return a.difficulty.localeCompare(b.difficulty); },
      origin: function (a, b) { return (a.originOrder || 99) - (b.originOrder || 99); }
    };

    // Every sort falls back to alphabetical so the order is always stable.
    var cmp = by[state.sort] || by.alpha;
    rows.sort(function (a, b) { return cmp(a, b) || by.alpha(a, b); });

    render(rows);
  }

  /* ---------------------------------------------------------------- render */

  function render(rows) {
    empty.hidden = rows.length > 0;

    grid.innerHTML = rows.map(function (r) {
      var sdp = typeof r.perfects === 'number' && r.perfects < 10;
      var tags = [
        '<span class="pill pill--' + r.difficulty.toLowerCase() + '">' + DDR.diffLabel(r.difficulty) + '</span>',
        r.level ? '<span class="pill pill--lvl">Lv.' + r.level + '</span>' : '',
        r.origin ? '<span class="pill pill--origin">' + DDR.esc(r.origin) + '</span>' : ''
      ].join('');

      return '' +
        '<button class="record' + (sdp ? ' record--sdp' : '') + '" type="button" data-id="' + DDR.esc(r.source) + '|' + r.difficulty + '">' +
          DDR.jacketHtml(r, 'record__jacket') +
          '<span class="record__body">' +
            '<span class="record__title">' + DDR.esc(r.title) + '</span>' +
            (r.titleAlt ? '<span class="record__alt">' + DDR.esc(r.titleAlt) + '</span>' : '') +
            '<span class="record__tags">' + tags + '</span>' +
          '</span>' +
          '<span class="record__score">' +
            '<span class="record__score-value">' + (r.score === null ? '—' : DDR.num(r.score)) + '</span>' +
            '<span class="record__score-sub">' + (r.perfects === null ? 'unlogged' : r.perfects + 'P') + '</span>' +
          '</span>' +
        '</button>';
    }).join('');
  }

  /* ---------------------------------------------------------------- drawer */

  grid.addEventListener('click', function (e) {
    var card = e.target.closest('.record');
    if (!card) return;
    var parts = card.dataset.id.split('|');
    var record = records.filter(function (r) {
      return r.source === parts[0] && r.difficulty === parts[1];
    })[0];
    if (record) DDR.openDrawer(record);
  });

  /* --------------------------------------------------------------- controls */

  var debounce;
  $('#q').addEventListener('input', function (e) {
    clearTimeout(debounce);
    var value = e.target.value;
    debounce = setTimeout(function () { state.q = value; apply(); }, 140);
  });

  $('#difficulty').addEventListener('change', function (e) {
    state.diff = e.target.value;
    apply();
  });

  ['level', 'origin', 'sort'].forEach(function (key) {
    $('#' + key).addEventListener('change', function (e) {
      state[key] = e.target.value;
      apply();
    });
  });


  apply();
}());
