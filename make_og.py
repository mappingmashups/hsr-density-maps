"""Link-preview image (docs/og.png, 1200×630) for Slack, social media and messaging apps.

Opens the built page in headless Chromium and frames the heading plus the
comparison chart in its default view (San Francisco–LA against Madrid–Barcelona). Run after build_page.py.

Needs Playwright with Chromium (pip install playwright; playwright install chromium),
or set CHROMIUM to an existing browser binary.

Usage: python make_og.py
"""
import asyncio, base64, functools, http.server, os, threading
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
        pg = await b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2, color_scheme="light")
        await pg.goto(url); await pg.wait_for_timeout(1500)
        await pg.evaluate("localStorage.clear()")
        await pg.reload(); await pg.wait_for_timeout(1500)   # the page's default comparison view
        # capture the comparison at its natural size, then lay it out beside the heading as a picture
        await pg.add_style_tag(content=".secnav { display: none !important; }")   # keep the sticky menu out of the shot
        shot = await pg.locator("#cmp").screenshot()
        b64 = base64.b64encode(shot).decode()
        await pg.evaluate("""src => {
          const card = document.createElement('div');
          card.style.cssText = 'position:fixed;inset:0;background:var(--bg);z-index:100;display:grid;grid-template-columns:420px 1fr;gap:28px;padding:40px 44px;align-items:center';
          const h = document.querySelector('header h1').cloneNode(true);
          h.style.cssText = 'font-size:46px;line-height:1.04;max-width:none';
          const p = document.createElement('p');
          p.textContent = 'Population within 20 km of every station on 26 high-speed rail lines, at one scale. San Francisco–LA against Madrid–Barcelona.';
          p.style.cssText = 'font:400 19px/1.45 var(--f-body);color:var(--ink-2);margin-top:18px';
          const left = document.createElement('div'); left.append(h, p);
          const right = document.createElement('div');
          right.style.cssText = 'height:550px;background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:12px;display:grid;place-items:center;overflow:hidden';
          const img = new Image(); img.src = 'data:image/png;base64,' + src;
          img.style.cssText = 'max-width:100%;max-height:100%;object-fit:contain';
          right.append(img); card.append(left, right); document.body.append(card);
        }""", b64)
        await pg.wait_for_timeout(500)
        out = os.path.join(DOCS, "og.png")
        await pg.screenshot(path=out, clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        from PIL import Image   # rendered at 2x for crisp text; saved at the standard 1200×630
        Image.open(out).resize((1200, 630), Image.LANCZOS).save(out, optimize=True)
        await b.close()
    srv.shutdown()
    print("wrote docs/og.png")


if __name__ == "__main__":
    asyncio.run(main())
