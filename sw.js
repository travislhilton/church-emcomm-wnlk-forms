/* Church of Jesus Christ EMCOMM app service worker — keeps the portal and the three Worker forms on the phone so
   they open, capture GPS and save to the Outbox with no signal (registered by the Church of Jesus Christ EMCOMM app
   module, templates/_shared/emcomm-app.js, on https only; scope = the repository root on
   GitHub Pages). Network first, for NET_WAIT_MS at most: a phone with internet gets the latest
   copy and the cache is refreshed; a phone with no network, or one whose requests hang, gets the
   cached copy. Bump CACHE on every change to this file or the list below.
   Every file in FILES must exist in the repository (testing/test_offline_webkit.py checks it): an update
   that cannot get a file, and has no older copy of it, does not install and the old version stays. */
var CACHE = 'emcomm-app-2026-11-12.1';
var FILES = [
  'forms/index.html',
  'forms/comms.html',
  'forms/manifest.webmanifest',
  'forms/icons/icon-180.png',
  'forms/icons/icon-192.png',
  'forms/icons/icon-512.png',
  'forms/icons/icon-maskable-512.png',
  'forms/vendor/jsQR.js',
  'templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html',
  'templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Worker.html',
  'templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Worker.html',
  'training/quick-ref-cards.html',
  'training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf'
];

function oldCaches() {
  return caches.keys().then(function (keys) { return keys.filter(function (k) { return k.indexOf('emcomm-app-') === 0 && k !== CACHE; }); });
}

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    // one by one, so one failed download does not stop the rest from being cached
    return Promise.all(FILES.map(function (f) {
      return c.add(new Request(f, {cache: 'reload'})).then(function () { return null; }, function () { return f; });
    })).then(function (failed) {
      failed = failed.filter(Boolean);
      if (!failed.length) return;
      // a patchy update: keep the phone's older copy of each file that did not come down
      return oldCaches().then(function (olds) {
        return Promise.all(failed.map(function (f) {
          return olds.reduce(function (p, k) {
            return p.then(function (got) {
              if (got) return got;
              return caches.open(k).then(function (oc) { return oc.match(f, {ignoreSearch: true}); });
            });
          }, Promise.resolve(null)).then(function (hit) {
            return hit ? c.put(f, hit).then(function () { return null; }) : f;
          });
        })).then(function (still) {
          still = still.filter(Boolean);
          // an update that would lose a file: do not install; the old version keeps working and the
          // browser tries the update again later. The very first install keeps what it got.
          if (still.length && olds.length) {
            return caches.delete(CACHE).then(function () { throw new Error('update incomplete: ' + still.join(', ')); });
          }
        });
      });
    });
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(oldCaches().then(function (keys) {
    return Promise.all(keys.map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

// How long the network gets before the copy on the phone is used. An iPhone in airplane mode still
// reports itself online and its requests hang for more than a minute instead of failing, which left a
// black launch screen and dead buttons (field test 2026-10-31). A phone with working internet answers
// well inside this; the network copy still refreshes the cache in the background when it arrives.
var NET_WAIT_MS = 2500;

function isPage(req) {
  // a page the app can stand in for: an .html address or a folder, opened as a page
  if (req.mode !== 'navigate') return false;
  var p = new URL(req.url).pathname;
  return /\/$/.test(p) || /\.html?$/i.test(p);
}

function fromCache(req) {
  // the cached copy, ignoring ?eoc= / ?outbox= on the address; a page that is not saved opens the portal
  return caches.match(req, {ignoreSearch: true}).then(function (hit) {
    if (hit) return hit;
    if (!isPage(req)) return null;
    return caches.match('forms/index.html');
  });
}

var OFFLINE_TEXT = 'Not saved on this phone. Open it once with internet.';
function offline(req) {
  // anything else that is not on the phone: say so, with an error status (never the portal in its place)
  if (req.mode === 'navigate') {
    return new Response('<!DOCTYPE html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<title>Not saved on this phone</title><body style="font:18px system-ui,sans-serif;padding:24px;color:#1a3a5c">' +
      '<p><b>' + OFFLINE_TEXT + '</b></p><p><a href="' + self.registration.scope + 'forms/index.html">Back to the forms</a></p></body>',
      {status: 503, statusText: 'Offline', headers: {'Content-Type': 'text/html; charset=utf-8'}});
  }
  return new Response(OFFLINE_TEXT, {status: 503, statusText: 'Offline', headers: {'Content-Type': 'text/plain; charset=utf-8'}});
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;   // never touch the EOC server or GitHub
  var net = fetch(req).then(function (res) {
    if (res && res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { return c.put(req, copy); }).catch(function () {}); }
    return res;
  });
  e.waitUntil(net.catch(function () {}));   // let a slow network answer still refresh the cache
  e.respondWith(new Promise(function (resolve) {
    var done = false;
    function give(res) { if (!done && res) { done = true; resolve(res); } }
    function cacheOr(fallback) {
      return fromCache(req).then(function (hit) { if (hit) give(hit); else if (fallback) give(fallback()); });
    }
    var timer = setTimeout(function () { cacheOr(null); }, NET_WAIT_MS);   // slow: the phone's copy, if there is one
    net.then(function (res) {
      clearTimeout(timer);
      give(res);   // any answer from the server, as before
    }, function () {
      clearTimeout(timer);
      cacheOr(function () { return offline(req); });   // offline and not cached
    });
  }));
});
