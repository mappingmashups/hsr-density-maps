"""Link-preview image (docs/og.png, 1200×630) for Slack, social media and messaging apps.

Opens the built page in headless Chromium and frames the heading plus the
comparison chart in its default view (San Francisco–LA against Madrid–Barcelona). Run after build_page.py.

Needs Playwright with Chromium (pip install playwright; playwright install chromium),
or set CHROMIUM to an existing browser binary.

Usage: python make_og.py
"""
import asyncio, functools, http.server, os, threading
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=DOCS)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


async def main():
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    async with async_playwright() as p:
        exe = os.environ.get("CHROMIUM")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = await b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1, color_scheme="light")
        await pg.goto(url); await pg.wait_for_timeout(1500)
        await pg.evaluate("localStorage.clear()")
        await pg.reload(); await pg.wait_for_timeout(1500)   # the page's default comparison view
        # a self-contained card: page heading over the comparison chart
        await pg.evaluate("""() => {
          const card = document.createElement('div');
          card.id = 'og';
          card.style.cssText = 'position:fixed;inset:0;background:var(--bg);z-index:100;display:grid;grid-template-columns:420px 1fr;gap:28px;padding:44px 48px;align-items:center';
          const h = document.querySelector('header h1').cloneNode(true);
          h.style.cssText = 'font-size:46px;line-height:1.04;max-width:none';
          const p = document.createElement('p');
          p.textContent = 'Population within 20 km of every station on 26 high-speed rail lines, at one scale. San Francisco–LA against Madrid–Barcelona.';
          p.style.cssText = 'font:400 19px/1.45 var(--f-body);color:var(--ink-2);margin-top:18px';
          const left = document.createElement('div'); left.append(h, p);
          const cmp = document.querySelector('#cmp');   // moved, not copied, so it keeps its live drawing
          cmp.style.cssText = 'min-width:0;transform-origin:top left';
          const right = document.createElement('div'); right.style.cssText = 'height:542px;overflow:hidden;background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:14px';
          right.append(cmp); card.append(left, right); document.body.append(card);
          const s = Math.min(1, 512 / cmp.scrollHeight, (right.clientWidth - 28) / cmp.scrollWidth);
          cmp.style.transform = `scale(${s})`;
        }""")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(DOCS, "og.png"), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        await b.close()
    srv.shutdown()
    print("wrote docs/og.png")


if __name__ == "__main__":
    asyncio.run(main())
