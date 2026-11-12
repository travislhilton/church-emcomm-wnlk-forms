/* EMCOMM map module — the status map of the EOC Message Center (Map tab) and the wall display (map tile).
   SINGLE SOURCE: edit this file, then run  python installer/sync-app-module.py
   which copies it between the EMCOMM-MAP markers in eoc/EOC_Message_Center.html and eoc/EOC_Wall_Display.html.
   Never edit the copies.

   What it draws (docs/SIMULATOR_DESIGN.md section 6): the units of the geographic dataset
   (wards and branches at a Stake or Satellite EOC, stakes at a Council / Area EOC) as outlines
   filled by roster status, meetinghouses as dots, this EOC, and reports that carry a GPS fix.
   The dataset is served by the EOC server from the folder set on the Setup tab (/map/...).
   No external dependencies: Web Mercator on a canvas, like the simulator's map.

   var map = EMCOMM_MAP.create(canvasEl, {interactive: true, labels: true, minLabelPx: 11, onSelect: fn});
   map.load('/map').then(function(info){ ... });      // info.units, info.buildings
   map.setLevel('stake' | 'satellite' | 'area');      // which polygons are the "units"
   map.setStatus(function(unitName){ return {cls: 'none'|'ok'|'needs'|'alert'|'overdue'|'voice', text: '...'}; });
   map.setMarkers([{lon, lat, kind: 'eoc'|'report'|'parent', label: '...'}]);
   map.setFocus(['Alpha 1st Ward', ...]);               // fit() frames these units when any are on the map
   map.fit(); map.draw(); map.units() -> [{name, type, stake}], map.select(name)

   Basemap under the overlays (maintainer, 2026-11-12), chosen per browser (localStorage 'emcomm_basemap'):
     'streets'  OpenStreetMap, drawn live by this page when it has internet (never saved on the laptop);
                when its tiles fail it falls back to the saved Topo map, with the note "Street map needs internet"
     'topo', 'imagery'  USGS (United States Geological Survey) The National Map, saved on the EOC laptop
                (Setup tab) and served only by this EOC server from /basemap/<layer>/<z>/<y>/<x>
     'none'     the plain background.  Nothing chosen = Streets when it loads, otherwise Topo if saved.
   map.setBasemap('streets' | 'topo' | 'imagery' | 'none'); map.basemap() -> {choice, shown, note, attribution, drawn}
   map.refreshBasemap()   // after a download: read /api/basemap/status again
   opts.basemap: false turns it off; opts.onBasemap(state) hears when the shown layer or note changes.
*/
(function () {
  var R = 6378137, D2R = Math.PI / 180, WORLD = 2 * Math.PI * R;
  var BM_KEY = 'emcomm_basemap', BM_ATTR = {streets: '© OpenStreetMap contributors', topo: 'Basemap: USGS The National Map', imagery: 'Basemap: USGS The National Map'};
  var BM_WASH = {streets: 0.18, topo: 0.12, imagery: 0.32};   // a white wash keeps the overlays readable on top
  var bmStatus = null, bmStatusTs = 0, bmStatusP = null, bmListeners = [];
  function bmLoadStatus(force) {   // one status read per page, shared by every map on it
    if (bmStatusP && !force) return bmStatusP;
    bmStatusP = fetch('/api/basemap/status').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      .then(function (s) { bmStatus = s; bmStatusTs = Date.now(); bmListeners.forEach(function (fn) { try { fn(); } catch (e) {} }); return s; });
    return bmStatusP;
  }
  function bmSaved(layer) { var l = bmStatus && bmStatus.layers && bmStatus.layers[layer]; return !!(l && l.tiles > 0 && l.zooms); }
  function bmGetChoice() { try { return localStorage.getItem(BM_KEY) || ''; } catch (e) { return ''; } }
  function bmSetChoice(v) { try { if (v) localStorage.setItem(BM_KEY, v); else localStorage.removeItem(BM_KEY); } catch (e) {} }
  function merc(lon, lat) { return [R * lon * D2R, R * Math.log(Math.tan(Math.PI / 4 + Math.max(-85, Math.min(85, lat)) * D2R / 2))]; }
  var COLORS = {
    none:    {fill: 'rgba(148,163,184,.28)', line: '#64748b'},
    ok:      {fill: 'rgba(34,197,94,.45)',   line: '#15803d'},
    needs:   {fill: 'rgba(245,158,11,.50)',  line: '#b45309'},
    alert:   {fill: 'rgba(220,38,38,.55)',   line: '#991b1b'},
    overdue: {fill: 'rgba(148,163,184,.28)', line: '#d97706'},
    voice:   {fill: 'rgba(59,130,246,.42)',  line: '#1d4ed8'}
  };
  var MARK = {eoc: '#1d4ed8', parent: '#7c3aed', report: '#111827'};

  function norm(s) { return String(s || '').toLowerCase().replace(/\s+/g, ' ').trim(); }
  function bboxOf(rings) {
    var b = null;
    rings.forEach(function (ring) { ring.forEach(function (p) {
      if (!b) b = [p[0], p[1], p[0], p[1]];
      else { if (p[0] < b[0]) b[0] = p[0]; if (p[1] < b[1]) b[1] = p[1]; if (p[0] > b[2]) b[2] = p[0]; if (p[1] > b[3]) b[3] = p[1]; }
    }); });
    return b;
  }
  function pointInRings(x, y, polys) {   // even-odd over every ring of every polygon
    var inside = false;
    polys.forEach(function (rings) { rings.forEach(function (ring) {
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
        if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
      }
    }); });
    return inside;
  }

  function create(canvas, opts) {
    opts = opts || {};
    var ctx = canvas.getContext('2d'), W = 0, H = 0, dpr = 1;
    var view = {cx: 0, cy: 0, res: 50};
    var orgs = [], bldgs = [], markers = [], level = 'stake', statusFn = null, selected = null, loaded = false, loadError = '', focus = null;
    var labels = opts.labels !== false, minLabel = opts.minLabelPx || 11;

    function resize() {
      dpr = window.devicePixelRatio || 1;
      var r = canvas.getBoundingClientRect();
      W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function toScr(x, y) { return [(x - view.cx) / view.res + W / 2, H / 2 - (y - view.cy) / view.res]; }
    function fromScr(sx, sy) { return [view.cx + (sx - W / 2) * view.res, view.cy - (sy - H / 2) * view.res]; }
    function isUnit(o) { return level === 'area' ? o.type === 'Stake' : (o.type === 'Ward' || o.type === 'Branch'); }
    function isStakeOutline(o) { return level !== 'area' && o.type === 'Stake'; }

    function load(base) {
      base = (base || '/map').replace(/\/$/, '');
      return Promise.all([fetch(base + '/organization_boundaries.geojson').then(function (r) { if (!r.ok) throw new Error('boundaries: HTTP ' + r.status); return r.json(); }),
                          fetch(base + '/buildings.geojson').then(function (r) { return r.ok ? r.json() : {features: []}; }).catch(function () { return {features: []}; })])
        .then(function (res) {
          orgs = []; bldgs = [];
          (res[0].features || []).forEach(function (f) {
            var p = f.properties || {}, g = f.geometry; if (!g) return;
            var polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
            polys = polys.map(function (rings) { return rings.map(function (ring) { return ring.map(function (c) { return merc(c[0], c[1]); }); }); });
            if (!polys.length) return;
            var all = []; polys.forEach(function (rings) { rings.forEach(function (r) { all.push(r); }); });
            var o = {id: p.org_id, name: p.org_name || '', key: norm(p.org_name), type: p.org_type || '', stake: p.stake_id || '', polys: polys, bbox: bboxOf(all)};
            o.labelXY = p.label_longitude != null ? merc(p.label_longitude, p.label_latitude) : [(o.bbox[0] + o.bbox[2]) / 2, (o.bbox[1] + o.bbox[3]) / 2];
            orgs.push(o);
          });
          (res[1].features || []).forEach(function (f) {
            var p = f.properties || {}, g = f.geometry; if (!g || g.type !== 'Point') return;
            bldgs.push({xy: merc(g.coordinates[0], g.coordinates[1]), names: p.organization_names || [], id: p.building_id});
          });
          loaded = true; loadError = '';
          resize(); fit(); draw();
          return {units: orgs.filter(isUnit).length, buildings: bldgs.length, orgs: orgs.length};
        }).catch(function (e) { loaded = false; loadError = String(e.message || e); draw(); throw e; });
    }

    function fit(pad) {
      pad = pad || 0.92;
      var b = null;
      var mine = focus ? orgs.filter(function (o) { return isUnit(o) && o.bbox && focus[o.key]; }) : [];
      (mine.length ? mine : orgs).forEach(function (o) { if (!isUnit(o) || !o.bbox) return; b = b ? [Math.min(b[0], o.bbox[0]), Math.min(b[1], o.bbox[1]), Math.max(b[2], o.bbox[2]), Math.max(b[3], o.bbox[3])] : o.bbox.slice(); });
      if (!b) markers.forEach(function (m) { var xy = merc(m.lon, m.lat); b = b ? [Math.min(b[0], xy[0] - 3000), Math.min(b[1], xy[1] - 3000), Math.max(b[2], xy[0] + 3000), Math.max(b[3], xy[1] + 3000)] : [xy[0] - 3000, xy[1] - 3000, xy[0] + 3000, xy[1] + 3000]; });
      if (!b || !W) return;
      view.cx = (b[0] + b[2]) / 2; view.cy = (b[1] + b[3]) / 2;
      view.res = Math.max((b[2] - b[0]) / (W * pad), (b[3] - b[1]) / (H * pad), 0.05);
    }

    function tracePolys(polys) {
      ctx.beginPath();
      polys.forEach(function (rings) { rings.forEach(function (ring) {
        var lx = NaN, ly = NaN, first = true;
        for (var i = 0; i < ring.length; i++) {
          var sx = (ring[i][0] - view.cx) / view.res + W / 2, sy = H / 2 - (ring[i][1] - view.cy) / view.res;
          if (!first && Math.abs(sx - lx) < 0.6 && Math.abs(sy - ly) < 0.6) continue;
          if (first) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
          first = false; lx = sx; ly = sy;
        }
        ctx.closePath();
      }); });
    }
    function onScreen(b) { if (!b) return false; var a = toScr(b[0], b[3]), c = toScr(b[2], b[1]); return !(a[0] > W || c[0] < 0 || a[1] > H || c[1] < 0); }

    // ── basemap tiles (XYZ, Web Mercator): drawn first, everything else on top ──
    var bm = {on: opts.basemap !== false, choice: bmGetChoice(), tiles: {}, n: 0, streetsDown: false, retryAt: 0, backoff: 30000,
              failsInRow: 0, shown: '', note: '', lastKey: '', drawn: 0, queued: false};
    function bmRedraw() { if (bm.queued) return; bm.queued = true; setTimeout(function () { bm.queued = false; draw(); }, 60); }
    if (bm.on) { bmListeners.push(bmRedraw); bmLoadStatus(); }
    function bmLayer() {   // which layer to draw now, and the note to show
      if (!bm.on || !bmStatus) return {layer: '', note: ''};
      var c = bm.choice || 'streets';
      if (c === 'none') return {layer: '', note: ''};
      var saved = bmSaved('topo') ? 'topo' : bmSaved('imagery') ? 'imagery' : '';
      if (c === 'streets') {
        if (!bmStatus.streetsUrl) return {layer: saved, note: ''};
        if (bm.streetsDown && Date.now() >= bm.retryAt) {   // try the street map again, once, after the pause
          bm.streetsDown = false; bm.failsInRow = 0;
          Object.keys(bm.tiles).forEach(function (k) { if (k.indexOf('streets|') === 0 && bm.tiles[k].fail) { delete bm.tiles[k]; bm.n--; } });
        }
        if (!bm.streetsDown) return {layer: 'streets', note: ''};
        return {layer: saved, note: 'Street map needs internet' + (saved ? '. Showing the saved ' + (saved === 'topo' ? 'Topo' : 'Imagery') + ' map.' : '.')};
      }
      if (bmSaved(c)) return {layer: c, note: ''};
      return {layer: '', note: (c === 'topo' ? 'Topo' : 'Imagery') + ' map not saved on this laptop yet (Setup tab).'};
    }
    function bmUrl(layer, z, x, y) {
      if (layer === 'streets') return String(bmStatus.streetsUrl).replace('{z}', z).replace('{x}', x).replace('{y}', y);
      return '/basemap/' + layer + '/' + z + '/' + y + '/' + x;
    }
    function bmTile(layer, z, x, y, request) {
      var k = layer + '|' + z + '|' + x + '|' + y, t = bm.tiles[k];
      if (t || !request) return t;
      if (bm.n > 900) { var ks = Object.keys(bm.tiles); for (var i = 0; i < 300; i++) { delete bm.tiles[ks[i]]; } bm.n -= 300; }
      t = bm.tiles[k] = {img: new Image(), ok: false, fail: false}; bm.n++;
      if (layer === 'streets') t.img.crossOrigin = 'anonymous';
      t.img.onload = function () { t.ok = true; if (layer === 'streets') { bm.failsInRow = 0; bm.backoff = 30000; } bmRedraw(); };
      t.img.onerror = function () {
        t.fail = true;
        if (layer !== 'streets') return;
        bm.failsInRow++;
        var anyOk = Object.keys(bm.tiles).some(function (q) { return q.indexOf('streets|') === 0 && bm.tiles[q].ok; });
        if (!bm.streetsDown && (bm.failsInRow >= 3 || !anyOk)) {   // no internet: stop asking, back off, fall back
          bm.streetsDown = true; bm.retryAt = Date.now() + bm.backoff; bm.backoff = Math.min(bm.backoff * 2, 300000);
          bmRedraw();
        }
      };
      t.img.src = bmUrl(layer, z, x, y);
      return t;
    }
    function drawBasemap() {
      if (bm.on && bmStatus && Date.now() - bmStatusTs > 120000) bmLoadStatus(true);   // a download finished meanwhile
      var pick = bmLayer(), layer = pick.layer; bm.drawn = 0;
      if (layer) {
        var dz = Math.log(WORLD / 256 / view.res) / Math.LN2 + ((window.devicePixelRatio || 1) > 1 ? 0.3 : 0);
        var z = Math.round(dz), ranges = null;
        if (layer === 'streets') z = Math.max(0, Math.min(19, z));
        else {
          var info = bmStatus.layers[layer]; z = Math.max(info.zooms[0], Math.min(info.zooms[1], z));
          ranges = info.ranges && info.ranges[String(z)];
        }
        var ts = WORLD / Math.pow(2, z), n = Math.pow(2, z);
        var tl = fromScr(0, 0), br = fromScr(W, H);
        var x0 = Math.max(0, Math.floor((tl[0] + WORLD / 2) / ts)), x1 = Math.min(n - 1, Math.floor((br[0] + WORLD / 2) / ts));
        var y0 = Math.max(0, Math.floor((WORLD / 2 - tl[1]) / ts)), y1 = Math.min(n - 1, Math.floor((WORLD / 2 - br[1]) / ts));
        if (ranges) { x0 = Math.max(x0, ranges[0]); y0 = Math.max(y0, ranges[1]); x1 = Math.min(x1, ranges[2]); y1 = Math.min(y1, ranges[3]); }
        if (x1 >= x0 && y1 >= y0 && (x1 - x0 + 1) * (y1 - y0 + 1) <= 400) {
          for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) {
            var a = toScr(-WORLD / 2 + x * ts, WORLD / 2 - y * ts), c = toScr(-WORLD / 2 + (x + 1) * ts, WORLD / 2 - (y + 1) * ts);
            var dx = Math.floor(a[0]), dy = Math.floor(a[1]), dw = Math.ceil(c[0]) - dx, dh = Math.ceil(c[1]) - dy;
            var t = bmTile(layer, z, x, y, true);
            if (t.ok) { ctx.drawImage(t.img, dx, dy, dw, dh); bm.drawn++; continue; }
            for (var up = 1; up <= 4 && z - up >= 0; up++) {   // a coarser tile already here stands in while this one loads
              var p = bmTile(layer, z - up, x >> up, y >> up, false);
              if (p && p.ok) { var s = 256 / (1 << up); ctx.drawImage(p.img, (x - ((x >> up) << up)) * s, (y - ((y >> up) << up)) * s, s, s, dx, dy, dw, dh); break; }
            }
          }
          ctx.fillStyle = 'rgba(255,255,255,' + BM_WASH[layer] + ')'; ctx.fillRect(0, 0, W, H);
        }
      }
      var key = layer + '|' + pick.note;
      bm.shown = layer; bm.note = pick.note;
      if (key !== bm.lastKey) { bm.lastKey = key; if (opts.onBasemap) { try { opts.onBasemap(bmState()); } catch (e) {} } }
    }
    function drawBasemapText() {   // attribution whenever a basemap shows; the note when the chosen one cannot
      ctx.font = '11px system-ui, sans-serif'; ctx.textBaseline = 'middle';
      var lines = [];
      if (bm.shown) lines.push(BM_ATTR[bm.shown]);
      if (bm.note) lines.push(bm.note);
      lines.forEach(function (txt, i) {
        var w = ctx.measureText(txt).width + 10, yy = H - 14 - i * 18;
        ctx.fillStyle = 'rgba(255,255,255,.88)'; ctx.fillRect(W - w - 4, yy - 8, w, 16);
        ctx.fillStyle = '#1f2937'; ctx.textAlign = 'right'; ctx.fillText(txt, W - 9, yy);
      });
    }
    function bmState() { return {choice: bm.choice || 'streets', shown: bm.shown, note: bm.note, attribution: bm.shown ? BM_ATTR[bm.shown] : '', drawn: bm.drawn,
                                 saved: {topo: bmSaved('topo'), imagery: bmSaved('imagery')}, streets: !!(bmStatus && bmStatus.streetsUrl)}; }

    var images = [];   // [{img, b: [w, s, e, n] Web Mercator metres, opacity}]: the directory's own map artwork
    function draw() {
      if (!W) resize();
      ctx.fillStyle = opts.background || '#eef2f6'; ctx.fillRect(0, 0, W, H);
      if (loaded) drawBasemap();
      images.forEach(function (im) {
        if (!im.img.complete || !im.img.naturalWidth || !onScreen(im.b)) return;
        var a = toScr(im.b[0], im.b[3]), c = toScr(im.b[2], im.b[1]);
        ctx.globalAlpha = im.opacity; ctx.drawImage(im.img, a[0], a[1], c[0] - a[0], c[1] - a[1]); ctx.globalAlpha = 1;
      });
      if (!loaded) {
        ctx.fillStyle = '#64748b'; ctx.font = '13px system-ui, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText(loadError ? 'Map data not available: ' + loadError : 'Loading map data…', W / 2, H / 2);
        return;
      }
      // unit polygons, filled by status
      orgs.forEach(function (o) {
        if (!isUnit(o) || !onScreen(o.bbox)) return;
        var st = statusFn ? (statusFn(o.name) || {}) : {}, c = COLORS[st.cls] || COLORS.none;
        tracePolys(o.polys);
        ctx.fillStyle = c.fill; ctx.fill();
        ctx.lineWidth = st.cls === 'overdue' ? 3 : 1.2; ctx.strokeStyle = c.line;
        if (st.cls === 'overdue') ctx.setLineDash([6, 4]);
        ctx.stroke(); ctx.setLineDash([]);
        if (selected && o.key === selected) { ctx.lineWidth = 3; ctx.strokeStyle = '#111827'; ctx.stroke(); }
      });
      // stake outlines behind the wards, thin
      orgs.forEach(function (o) {
        if (!isStakeOutline(o) || !onScreen(o.bbox)) return;
        tracePolys(o.polys); ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(30,41,59,.55)'; ctx.stroke();
      });
      // meetinghouses
      bldgs.forEach(function (b) {
        var s = toScr(b.xy[0], b.xy[1]); if (s[0] < -6 || s[0] > W + 6 || s[1] < -6 || s[1] > H + 6) return;
        ctx.beginPath(); ctx.arc(s[0], s[1], 3.2, 0, Math.PI * 2); ctx.fillStyle = '#1e293b'; ctx.fill();
        ctx.lineWidth = 1; ctx.strokeStyle = '#fff'; ctx.stroke();
      });
      // labels (only when they fit: the unit's box must be wider than the text)
      if (labels) {
        ctx.font = 'bold ' + minLabel + 'px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        orgs.forEach(function (o) {
          if (!isUnit(o) || !onScreen(o.bbox)) return;
          var wpx = (o.bbox[2] - o.bbox[0]) / view.res, hpx = (o.bbox[3] - o.bbox[1]) / view.res;
          var txt = o.name.replace(/ (Ward|Branch|Stake)$/i, '');
          if (ctx.measureText(txt).width > wpx * 0.9 || hpx < minLabel * 2) return;
          var s = toScr(o.labelXY[0], o.labelXY[1]);
          ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.strokeText(txt, s[0], s[1]);
          ctx.fillStyle = '#0f172a'; ctx.fillText(txt, s[0], s[1]);
        });
      }
      // markers: reports as small squares, EOCs as rings
      markers.forEach(function (m) {
        if (m.lon == null || m.lat == null || isNaN(m.lon) || isNaN(m.lat)) return;
        var xy = merc(+m.lon, +m.lat), s = toScr(xy[0], xy[1]); if (s[0] < -12 || s[0] > W + 12 || s[1] < -12 || s[1] > H + 12) return;
        ctx.fillStyle = MARK[m.kind] || MARK.report;
        if (m.kind === 'report') { ctx.fillRect(s[0] - 3.5, s[1] - 3.5, 7, 7); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(s[0] - 3.5, s[1] - 3.5, 7, 7); }
        else { ctx.beginPath(); ctx.arc(s[0], s[1], 7, 0, Math.PI * 2); ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = '#fff'; ctx.stroke(); ctx.beginPath(); ctx.arc(s[0], s[1], 2.5, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); }
        if (labels && m.label) { ctx.font = 'bold ' + minLabel + 'px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.strokeText(m.label, s[0] + 10, s[1]); ctx.fillStyle = MARK[m.kind] || MARK.report; ctx.fillText(m.label, s[0] + 10, s[1]); }
      });
      // scale bar
      var target = 120 * view.res, step = Math.pow(10, Math.floor(Math.log(target) / Math.LN10)), n = target / step, len = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * step;
      var px = len / view.res, label = len >= 1000 ? (len / 1000) + ' km' : len + ' m';
      ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fillRect(8, H - 26, px + 16, 20);
      ctx.strokeStyle = '#111827'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(16, H - 12); ctx.lineTo(16 + px, H - 12); ctx.stroke();
      ctx.fillStyle = '#111827'; ctx.font = '11px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom'; ctx.fillText(label, 16, H - 14);
      drawBasemapText();
    }

    function unitAt(sx, sy) {
      var p = fromScr(sx, sy), hit = null;
      orgs.forEach(function (o) { if (isUnit(o) && o.bbox && p[0] >= o.bbox[0] && p[0] <= o.bbox[2] && p[1] >= o.bbox[1] && p[1] <= o.bbox[3] && pointInRings(p[0], p[1], o.polys)) hit = o; });
      return hit;
    }
    function zoomAt(f, sx, sy) { var m = fromScr(sx, sy); view.res = Math.min(Math.max(view.res / f, 0.05), 50000); var n = fromScr(sx, sy); view.cx += m[0] - n[0]; view.cy += m[1] - n[1]; draw(); }

    if (opts.interactive) {
      var drag = null, moved = false;
      canvas.style.cursor = 'grab';
      canvas.addEventListener('mousedown', function (e) { drag = {x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy}; moved = false; canvas.style.cursor = 'grabbing'; });
      window.addEventListener('mousemove', function (e) { if (!drag) return; var dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) moved = true; view.cx = drag.cx - dx * view.res; view.cy = drag.cy + dy * view.res; draw(); });
      window.addEventListener('mouseup', function (e) {
        if (!drag) return; var was = moved; drag = null; canvas.style.cursor = 'grab'; if (was) return;
        var r = canvas.getBoundingClientRect(), o = unitAt(e.clientX - r.left, e.clientY - r.top);
        selected = o ? o.key : null; draw(); if (opts.onSelect) opts.onSelect(o ? {name: o.name, type: o.type, stake: o.stake} : null);
      });
      canvas.addEventListener('wheel', function (e) { e.preventDefault(); var r = canvas.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - r.left, e.clientY - r.top); }, {passive: false});
      canvas.addEventListener('dblclick', function (e) { var r = canvas.getBoundingClientRect(); zoomAt(2, e.clientX - r.left, e.clientY - r.top); });
      // touch: one finger pans, pinch zooms
      var tp = null;
      canvas.addEventListener('touchstart', function (e) { if (e.touches.length === 1) tp = {x: e.touches[0].clientX, y: e.touches[0].clientY, cx: view.cx, cy: view.cy}; else if (e.touches.length === 2) tp = {d: Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY), res: view.res}; }, {passive: true});
      canvas.addEventListener('touchmove', function (e) { if (!tp) return; e.preventDefault(); if (e.touches.length === 1 && tp.x != null) { view.cx = tp.cx - (e.touches[0].clientX - tp.x) * view.res; view.cy = tp.cy + (e.touches[0].clientY - tp.y) * view.res; } else if (e.touches.length === 2 && tp.d) { var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); view.res = Math.min(Math.max(tp.res * tp.d / Math.max(d, 1), 0.05), 50000); } draw(); }, {passive: false});
      canvas.addEventListener('touchend', function () { tp = null; }, {passive: true});
    }
    window.addEventListener('resize', function () { if (canvas.offsetWidth) { resize(); draw(); } });

    return {
      load: load, draw: draw, resize: resize,
      fit: function () { resize(); fit(); draw(); },
      zoom: function (f) { zoomAt(f, W / 2, H / 2); },
      setLevel: function (l) { level = l === 'area' ? 'area' : (l || 'stake'); },
      setStatus: function (fn) { statusFn = fn; },
      setMarkers: function (list) { markers = list || []; },
      setImages: function (list) {   // [{url, bounds: [w, s, e, n] Web Mercator metres, opacity}]
        images = (list || []).map(function (o) { var img = new Image(); img.onload = draw; img.src = o.url; return {img: img, b: o.bounds, opacity: o.opacity == null ? 0.6 : o.opacity}; });
        draw();
      },
      focusOn: function (b) { if (!b) return; resize(); view.cx = (b[0] + b[2]) / 2; view.cy = (b[1] + b[3]) / 2; view.res = Math.max((b[2] - b[0]) / (W || 1), (b[3] - b[1]) / (H || 1)) * 1.05; draw(); },
      setFocus: function (names) { focus = null; if (names && names.length) { focus = {}; names.forEach(function (n) { focus[norm(n)] = true; }); } },
      select: function (name) { selected = name ? norm(name) : null; draw(); },
      units: function () { return orgs.filter(isUnit).map(function (o) { return {name: o.name, type: o.type, stake: o.stake}; }); },
      loaded: function () { return loaded; },
      setBasemap: function (c) {
        bm.choice = {streets: 1, topo: 1, imagery: 1, none: 1}[c] ? c : '';
        bmSetChoice(bm.choice); bm.streetsDown = false; bm.failsInRow = 0; bm.backoff = 30000; draw();
      },
      basemap: bmState,
      refreshBasemap: function () { return bmLoadStatus(true); },
      norm: norm
    };
  }
  window.EMCOMM_MAP = {create: create, merc: merc, basemapStatus: function (force) { return bmLoadStatus(force); }};
})();
