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

  // bindFields — unified per-page wiring
  // map  = { character: '<id>', story: '<id>', style: '<id>' }
  // opts = { debounce: 300, populate: true, onRemote: (vals) => {} }
  // returns { repopulate }
  function bindFields(map, opts) {
    opts = opts || {};
    var debounceMs = (opts.debounce != null) ? opts.debounce : 300;
    var doPopulate = (opts.populate !== false);
    var onRemote   = opts.onRemote || null;

    // Resolve elements
    var els = {};
    FIELDS.forEach(function (f) {
      if (map[f]) {
        var el = document.getElementById(map[f]);
        if (el) els[f] = el;
      }
    });

    function repopulate() {
      var s = read();
      FIELDS.forEach(function (f) {
        if (els[f]) els[f].value = s[f];
      });
    }

    // Optionally populate immediately
    if (doPopulate) repopulate();

    // Attach input listeners per field (debounced or immediate)
    FIELDS.forEach(function (f) {
      if (!els[f]) return;
      var timer = null;
      els[f].addEventListener('input', function () {
        var val = els[f].value;
        if (debounceMs === 0) {
          var part = {}; part[f] = val;
          patch(part);
        } else {
          clearTimeout(timer);
          timer = setTimeout(function () {
            var part = {}; part[f] = val;
            patch(part);
          }, debounceMs);
        }
      });
    });

    // Register ONE cross-tab listener — assigns .value directly, no synthetic events
    onExternalChange(function (vals) {
      FIELDS.forEach(function (f) {
        if (els[f]) els[f].value = vals[f];
      });
      if (onRemote) onRemote(vals);
    });

    return { repopulate: repopulate };
  }

  return { read: read, patch: patch, onExternalChange: onExternalChange, bindFields: bindFields, KEY: KEY, FIELDS: FIELDS };
})();
