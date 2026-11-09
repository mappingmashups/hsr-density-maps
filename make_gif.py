"""Square animated GIF of the default comparison (San Francisco–LA vs Madrid–Barcelona)
with the catchment radius sweeping 5 → 50 → 5 km: docs/compare_ca_es_radius.gif (800×800).

Opens the built page in headless Chromium, frames the comparison under a title,
captures one frame per km and assembles them with ffmpeg (shared palette).
Run after build_page.py. Needs Playwright with Chromium (or set CHROMIUM) and ffmpeg.

Usage: python make_gif.py
"""
import asyncio, os, shutil, subprocess, tempfile
from playwright.async_api import async_playwright
from make_og import serve, DOCS

S, OUT_PX, FPS, HOLD = 1080, 800, 12, 12   # capture size, output size, frames/s, frames held at 5 and 50 km


async def capture(url, frames):
    async with async_playwright() as p:
        exe = os.environ.get("CHROMIUM")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = await b.new_page(viewport={"width": S, "height": S}, device_scale_factor=1, color_scheme="light")
        await pg.goto(url); await pg.wait_for_timeout(1500)
        await pg.evaluate("localStorage.clear()"); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.add_style_tag(content=".secnav,.fliprow{display:none!important}")
        await pg.evaluate("""S => {
          const box = document.createElement('div');
          box.style.cssText = `position:fixed;left:0;top:0;width:${S}px;height:${S}px;background:var(--bg);z-index:100;padding:34px 40px;box-sizing:border-box;display:grid;grid-template-rows:auto 1fr;gap:14px;overflow:hidden`;
          const head = document.createElement('div');
          head.innerHTML = `<div style="font:800 34px/1.1 var(--f-display);color:var(--ink)">How many people live near the station?</div>
            <div style="font:400 20px/1.4 var(--f-display);color:var(--ink-2);margin-top:8px">San Francisco–LA vs Madrid–Barcelona · residents within <b id="gifR" style="color:var(--ink)">20 km</b> of each stop</div>`;
          const wrap = document.createElement('div');
          wrap.style.cssText = 'position:relative;overflow:hidden;background:var(--surface);border:1px solid var(--rule);border-radius:12px';
          const cmp = document.querySelector('#cmp');
          cmp.style.cssText = 'width:1000px;min-width:0;transform-origin:top left;position:absolute;left:0;top:0;padding:14px';
          wrap.append(cmp); box.append(head, wrap); document.body.append(box);
          window.__fit = () => { const s = Math.min(wrap.clientWidth / cmp.scrollWidth, wrap.clientHeight / cmp.scrollHeight);
            cmp.style.transform = `scale(${s})`; cmp.style.left = ((wrap.clientWidth - cmp.scrollWidth * s) / 2) + 'px'; };
        }""", S)
        seq = list(range(5, 51)) + list(range(49, 4, -1))
        n = 0
        for r in seq:
            await pg.evaluate(f"""() => {{ const i = document.getElementById('cmpRad'); i.value = {r}; i.dispatchEvent(new Event('input'));
              document.getElementById('gifR').textContent = '{r} km'; }}""")
            await pg.wait_for_timeout(60); await pg.evaluate("window.__fit()"); await pg.wait_for_timeout(40)
            first = os.path.join(frames, f"{n:04d}.png")
            await pg.screenshot(path=first, clip={"x": 0, "y": 0, "width": S, "height": S}); n += 1
            for _ in range(HOLD - 1 if r in (5, 50) and (r == 50 or n == 1) else 0):   # pause at the ends
                shutil.copy(first, os.path.join(frames, f"{n:04d}.png")); n += 1
        await b.close()


def main():
    srv = serve()
    out = os.path.join(DOCS, "compare_ca_es_radius.gif")
    with tempfile.TemporaryDirectory() as frames:
        asyncio.run(capture(f"http://127.0.0.1:{srv.server_address[1]}/", frames))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "%04d.png"),
                        "-vf", f"scale={OUT_PX}:{OUT_PX}:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];"
                               "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                        "-loop", "0", out], check=True)
    srv.shutdown()
    print("wrote", os.path.relpath(out))


if __name__ == "__main__":
    main()
