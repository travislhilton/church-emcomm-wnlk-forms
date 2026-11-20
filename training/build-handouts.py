#!/usr/bin/env python3
"""Build the printed handouts and the business card sheet as PDFs (training/handouts/pdf/).

  python training/build-handouts.py

Needs Playwright with Chromium (python -m pip install playwright; python -m playwright install chromium).
For every page it checks: Letter size, the expected page count (one per handout, two for the card sheet),
nothing running past the page, on the business card no text touching the QR panel or within 0.12 in
of a cut line, and every QR (Quick Response) code decoding (forms/vendor/jsQR.js) to the
address written in its data-url. Exit 1 on any failure.
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / 'training' / 'handouts'
OUT = SRC / 'pdf'
PAGES = [  # (source, PDF name, pages)
    ('handout-1-field-reports.html', 'Handout_1_Field_Reports_Without_an_EOC.pdf', 1),
    ('handout-2-eoc-flow.html', 'Handout_2_The_EOC_Flow.pdf', 1),
    ('handout-3-simulator.html', 'Handout_3_The_Simulator.pdf', 1),
    ('business-card-avery-5371.html', 'Business_Cards_Avery_5371.pdf', 2),
    ('business-card-avery-5371.html?test=1', 'Business_Cards_Avery_5371_Alignment_Test.pdf', 2),  # plain paper, held over a card sheet
]

CHECK_QR = """async () => {
  const out = [];
  for (const el of document.querySelectorAll('.qr[data-url]')) {
    if (!el.offsetParent) continue;   // not shown (the alignment test hides the cards)
    const svg = el.querySelector('svg'); if (!svg) { out.push([el.dataset.url, null]); continue; }
    const img = new Image(); const n = 400;
    img.src = 'data:image/svg+xml;base64,' + btoa(new XMLSerializer().serializeToString(svg));
    await img.decode();
    const c = document.createElement('canvas'); c.width = c.height = n;
    const x = c.getContext('2d'); x.drawImage(img, 0, 0, n, n);
    const r = jsQR(x.getImageData(0, 0, n, n).data, n, n);
    out.push([el.dataset.url, r ? r.data : null]);
  }
  return out;
}"""

CARD_CLEAR = """() => {   // business card: no text or drawing outside the QR panel touches it; all of it 0.12 in inside the cut
  const bad = [], IN = 96;
  for (const card of document.querySelectorAll('.card-sheet .card')) {
    if (!card.offsetParent) continue;
    const c = card.getBoundingClientRect(), blob = card.querySelector('.blob').getBoundingClientRect(), qb = card.querySelector('.qrbox');
    const boxes = [], w = document.createTreeWalker(card, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) boxes.push([n.textContent.trim(), b, qb.contains(n)]); }
    for (const s of card.querySelectorAll('svg')) if (!qb.contains(s)) boxes.push(['(drawing)', s.getBoundingClientRect(), false]);
    for (const [t, b, inPanel] of boxes) {
      if (!inPanel && b.right > blob.left - 4 && b.left < blob.right + 4 && b.top < blob.bottom + 4 && b.bottom > blob.top - 4) bad.push(t + ': touches the QR panel');
      if (Math.min(b.left - c.left, c.right - b.right, b.top - c.top, c.bottom - b.bottom) < 0.12 * IN) bad.push(t + ': closer than 0.12 in to the cut');
    }
  }
  return [...new Set(bad)];
}"""

OVERFLOW = """() => [...document.querySelectorAll('.page')].map(p => {
  const r = p.getBoundingClientRect(); let m = 0;
  p.querySelectorAll('*').forEach(e => { const b = e.getBoundingClientRect(); if (b.height) m = Math.max(m, b.bottom); });
  return Math.round(m - r.bottom);
})"""


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(exist_ok=True)
    fails = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1000, 'height': 1200})
        for src, pdf, want in PAGES:
            name, _, query = src.partition('?')
            pg.goto((SRC / name).as_uri() + ('?' + query if query else ''))
            pg.add_script_tag(path=str(REPO / 'forms' / 'vendor' / 'jsQR.js'))
            pg.wait_for_timeout(300)
            over = [o for o in pg.evaluate(OVERFLOW) if o > 0]
            qrs = pg.evaluate(CHECK_QR)
            clash = pg.evaluate(CARD_CLEAR)
            bad = [u for u, got in qrs if got != u]
            pg.emulate_media(media='print')
            data = pg.pdf(path=str(OUT / pdf), prefer_css_page_size=True, print_background=True)
            pg.emulate_media(media='screen')
            pages = data.count(b'/Type /Page') - data.count(b'/Type /Pages')
            ok = not over and not bad and not clash and pages == want
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {pdf}: {pages} page(s) (want {want}), {len(qrs)} QR codes"
                  + (f", {len(bad)} do not decode: {bad}" if bad else '') + (f", runs {over} px past the page" if over else '') + (f", card layout: {clash}" if clash else ''))
        b.close()
    print('\nAll handouts built.' if not fails else f'\n{fails} to fix.')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
