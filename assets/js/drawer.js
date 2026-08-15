/* ==========================================================================
   Shared record detail drawer + song artwork helpers.

   Used by the archive on My Records and by the hall of fame on the home page,
   so a card opens the same panel wherever it is clicked. Loaded after app.js
   and before the per-page script; it wires itself up if the page contains the
   drawer markup.
   ========================================================================== */

(function () {
  'use strict';

  var DDR = window.DDR || (window.DDR = {});
  var $ = DDR.$;

  // Stand-in result photo shown until real per-record proof shots exist. Give a
  // record a `proof` path in records.json and it takes over automatically.
  var PROOF_PLACEHOLDER = 'assets/img/proof/sample-proof.jpg';

  /* ---------------------------------------------------------------- helpers */

  DDR.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  };

  DDR.diffLabel = function (d) { return d === 'CSP' ? 'Challenge' : 'Expert'; };

  /**
   * Songs from before DDR adopted square jacket art have no artwork anywhere,
   * so they get a generated tile instead: a stable hue from the title plus
   * either its wide banner or its first character. Deterministic, so a song
   * always looks the same.
   */
  DDR.placeholderHtml = function (r) {
    var seed = 0;
    var key = r.title || r.source || '';
    for (var i = 0; i < key.length; i++) {
      seed = (seed * 31 + key.charCodeAt(i)) % 100000;
    }
    // Kept inside the site's cyan → violet → magenta arc.
    var hue = 186 + (seed % 145);
    var inner = r.banner
      ? '<img src="assets/img/banners/' + encodeURI(r.banner) + '" alt="" loading="lazy" />'
      : '<span>' + DDR.esc((key.match(/[0-9A-Za-z぀-ヿ㐀-鿿]/) || ['♪'])[0].toUpperCase()) + '</span>';
    return '<span class="jacket-ph" style="--ph-h:' + hue + '">' + inner + '</span>';
  };

  DDR.jacketHtml = function (r, cls) {
    if (r.jacket) {
      return '<div class="' + cls + '"><img src="assets/img/jackets/' + encodeURI(r.jacket) +
        '" alt="" loading="lazy" width="150" height="150" /></div>';
    }
    return '<div class="' + cls + '">' + DDR.placeholderHtml(r) + '</div>';
  };

  /** The result-screen photo that backs up the score. */
  function proofHtml(record) {
    var src = record.proof || PROOF_PLACEHOLDER;
    var real = Boolean(record.proof);
    return '' +
      '<section class="proof">' +
        '<div class="proof__head">' +
          '<p class="eyebrow">Proof</p>' +
          '<span class="proof__tag">' + (real ? 'Result screen' : 'Placeholder') + '</span>' +
        '</div>' +
        '<button class="proof__frame" type="button" data-proof="' + DDR.esc(src) + '" ' +
          'aria-label="Enlarge result photo">' +
          '<img src="' + DDR.esc(src) + '" alt="Result screen for ' + DDR.esc(record.title) + '" loading="lazy" />' +
        '</button>' +
        '<p class="proof__caption">' + (real
          ? 'Photographed at the cabinet. Tap to enlarge.'
          : 'Sample photo — real result shots not attached yet. Tap to enlarge.') +
        '</p>' +
      '</section>';
  }

  /* ----------------------------------------------------------------- wiring */

  var drawer = $('#drawer');
  var scrim = $('#scrim');
  if (!drawer || !scrim) return;          // page has no drawer markup

  var lastFocus = null;

  /* Full-screen view for the proof photo, built once and reused. */
  var lightbox = document.createElement('div');
  lightbox.className = 'lightbox';
  // Built with createElement rather than innerHTML so it never carries an empty
  // src, which browsers treat as a request for the current page.
  var lightboxImg = document.createElement('img');
  lightboxImg.alt = 'Result screen, enlarged';
  lightbox.appendChild(lightboxImg);
  document.body.appendChild(lightbox);

  function openLightbox(src) {
    lightboxImg.src = src;
    lightbox.classList.add('is-open');
  }
  function closeLightbox() {
    lightbox.classList.remove('is-open');
  }
  lightbox.addEventListener('click', closeLightbox);

  DDR.openDrawer = function (record) {
    var rows = [
      ['Difficulty', DDR.diffLabel(record.difficulty) + ' · Single Play'],
      ['Level', record.level ? 'Lv.' + record.level : 'Unrated on the 1–20 scale'],
      ['Perfects', record.perfects === null ? 'Not logged' : record.perfects],
      ['Origin', record.origin || 'Unknown'],
      ['Artist', record.artist || '—'],
      ['BPM', record.bpm || '—']
    ];

    if (record.history && record.history.length > 1) {
      rows.push(['Improved from', record.history.slice().sort(function (a, b) { return b - a; })
        .map(function (p) { return p + 'P'; }).join('  →  ')]);
    }
    if (record.source !== record.title) {
      rows.push(['Logged as', record.source]);
    }

    $('#drawer-body').innerHTML = '' +
      DDR.jacketHtml(record, 'drawer__jacket') +
      '<p class="eyebrow">' + (typeof record.perfects === 'number' && record.perfects < 10
        ? 'Single Digit Perfect' : 'Perfect Full Combo') + '</p>' +
      '<h2 class="drawer__title" id="drawer-title">' + DDR.esc(record.title) + '</h2>' +
      (record.titleAlt ? '<p class="drawer__alt">' + DDR.esc(record.titleAlt) + '</p>' : '') +
      '<p class="drawer__score">' + (record.score === null ? '—' : DDR.num(record.score)) + '</p>' +
      '<dl class="spec">' + rows.map(function (row) {
        return '<div><dt>' + DDR.esc(row[0]) + '</dt><dd>' + DDR.esc(row[1]) + '</dd></div>';
      }).join('') + '</dl>' +
      (record.remy
        ? '<a class="drawer__link" href="' + DDR.esc(record.remy) + '" target="_blank" rel="noopener">' +
          'Song page on RemyWiki ↗</a>'
        : '') +
      proofHtml(record);

    lastFocus = document.activeElement;
    drawer.hidden = false;
    // Next frame, so the transform transition actually runs.
    requestAnimationFrame(function () {
      drawer.classList.add('is-open');
      scrim.classList.add('is-open');
    });
    $('#drawer-close').focus();
    document.body.style.overflow = 'hidden';
  };

  function closeDrawer() {
    drawer.classList.remove('is-open');
    scrim.classList.remove('is-open');
    document.body.style.overflow = '';
    setTimeout(function () { drawer.hidden = true; }, 380);
    if (lastFocus) lastFocus.focus();
  }

  drawer.addEventListener('click', function (e) {
    var frame = e.target.closest('.proof__frame');
    if (frame) openLightbox(frame.dataset.proof);
  });

  scrim.addEventListener('click', closeDrawer);
  $('#drawer-close').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    // The lightbox sits above the drawer, so it closes first.
    if (lightbox.classList.contains('is-open')) closeLightbox();
    else if (!drawer.hidden) closeDrawer();
  });
}());
