/* ==========================================================================
   About: tab switching between the story sections.
   ========================================================================== */

(function () {
  'use strict';

  var DDR = window.DDR;
  var tabs = DDR.$$('.tabs__btn').filter(function (b) { return !b.disabled; });
  if (!tabs.length) return;

  function select(tab) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', String(on));
      var panel = document.getElementById(t.getAttribute('aria-controls'));
      if (panel) panel.hidden = !on;
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () { select(tab); });

    // Left/right arrows move between tabs, as expected of a tablist.
    tab.addEventListener('keydown', function (e) {
      var i = tabs.indexOf(tab);
      var next = e.key === 'ArrowRight' ? tabs[i + 1]
               : e.key === 'ArrowLeft' ? tabs[i - 1]
               : null;
      if (!next) return;
      e.preventDefault();
      next.focus();
      select(next);
    });
  });
}());
