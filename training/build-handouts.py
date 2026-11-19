#!/usr/bin/env python3
"""Build the printed handouts and the business card sheet as PDFs (training/handouts/pdf/).

  python training/build-handouts.py

Needs Playwright with Chromium (python -m pip install playwright; python -m playwright install chromium).
For every page it checks: Letter size, the expected page count (one per handout, two for the card sheet),
nothing running past the page, and every QR (Quick Response) code decoding (forms/vendor/jsQR.js) to the
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
]

CHECK_QR = """async () => {
  const out = [];
  for (const el of document.querySelectorAll('.qr[data-url]')) {
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
            pg.goto((SRC / src).as_uri())
            pg.add_script_tag(path=str(REPO / 'forms' / 'vendor' / 'jsQR.js'))
            pg.wait_for_timeout(300)
            over = [o for o in pg.evaluate(OVERFLOW) if o > 0]
            qrs = pg.evaluate(CHECK_QR)
            bad = [u for u, got in qrs if got != u]
            pg.emulate_media(media='print')
            data = pg.pdf(path=str(OUT / pdf), prefer_css_page_size=True, print_background=True)
            pg.emulate_media(media='screen')
            pages = data.count(b'/Type /Page') - data.count(b'/Type /Pages')
            ok = not over and not bad and pages == want
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {pdf}: {pages} page(s) (want {want}), {len(qrs)} QR codes"
                  + (f", {len(bad)} do not decode: {bad}" if bad else '') + (f", runs {over} px past the page" if over else ''))
        b.close()
    print('\nAll handouts built.' if not fails else f'\n{fails} to fix.')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
