/* shared_inputs.js — cross-tab shared inputs store (plain script, sets window.SharedInputs) */
/* Loaded as non-module <script> BEFORE each page's own script. */
window.SharedInputs = (function () {
  'use strict';

  var KEY    = 'monkeyking_shared_inputs';
  var FIELDS = ['character', 'style', 'story'];

  function read() {
    try {
      var r = JSON.parse(localStorage.getItem(KEY) || '{}');
      return {
        character: r.character != null ? r.character : '',
        style:     r.style     != null ? r.style     : '',
        story:     r.story     != null ? r.story     : '',
      };
    } catch (e) {
      return { character: '', style: '', story: '' };
    }
  }

  function patch(part) {
    var cur  = read();
    var next = {};
    FIELDS.forEach(function (f) { next[f] = f in part ? part[f] : cur[f]; });
    // Skip write if nothing changed
    if (FIELDS.every(function (f) { return next[f] === cur[f]; })) return;
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch (e) { /* quota / private-mode */ }
  }

  function onExternalChange(cb) {
    window.addEventListener('storage', function (e) {
      if (e.key !== KEY) return;
      cb(read());
    });
  }

  return { read: read, patch: patch, onExternalChange: onExternalChange, KEY: KEY, FIELDS: FIELDS };
})();
