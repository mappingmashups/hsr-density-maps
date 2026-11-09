"""Square animated GIF of a two-corridor comparison with the catchment radius sweeping
5 → 50 → 5 km: docs/compare_<left>_<right>_radius.gif (800×800).

Opens the built page in headless Chromium, frames the comparison under a title,
captures one frame per km and assembles them with ffmpeg (shared palette).
Run after build_page.py. Needs Playwright with Chromium (or set CHROMIUM) and ffmpeg.

Usage: python make_gif.py                          # San Francisco–LA vs Madrid–Barcelona (the page's default view)
       python make_gif.py cascadia de             # any two corridor ids from stations.py
       python make_gif.py ca fr --slide 0 --flip-right
       python make_gif.py cascadia de --mp4        # also a 1080×1080 H.264 video for Instagram (out/*.mp4)
"""
import argparse, asyncio, os, shutil, subprocess, tempfile
from playwright.async_api import async_playwright
from make_og import serve, DOCS

S, OUT_PX, FPS, HOLD = 1080, 800, 12, 12   # capture size, output size, frames/s, frames held at 5 and 50 km


async def capture(url, frames, a):
    async with async_playwright() as p:
        exe = os.environ.get("CHROMIUM")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = await b.new_page(viewport={"width": S, "height": S}, device_scale_factor=1, color_scheme="light")
        await pg.goto(url); await pg.wait_for_timeout(1500)
        await pg.evaluate("localStorage.clear()"); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.select_option("#cmpL", a.left); await pg.select_option("#cmpR", a.right); await pg.wait_for_timeout(300)
        for side, flip in (("L", a.flip_left), ("R", a.flip_right)):
            if flip:
                await pg.click(f"#cmpH{side} .flip"); await pg.wait_for_timeout(200)
        if a.slide is not None:
            await pg.evaluate(f"(() => {{ const i = document.getElementById('cmpSlide'); i.value = {a.slide}; i.dispatchEvent(new Event('input')); }})()")
            await pg.wait_for_timeout(200)
        names = [await pg.evaluate(f"document.querySelector('#cmp{s} option:checked').textContent") for s in "LR"]
        short = lambda n: n.split(" – ")[0] + "–" + n.split(" – ")[-1]
        await pg.add_style_tag(content=".secnav,.fliprow{display:none!important}")
        if await pg.is_checked("#cmpMsa"):   # population near stations only: no official metro bars or county outlines
            await pg.click("#cmpMsa"); await pg.wait_for_timeout(300)
        await pg.mouse.move(S - 2, 2)   # park the pointer so no station is hover-highlighted
        await pg.evaluate("""([S, title]) => {
          const box = document.createElement('div');
          box.style.cssText = `position:fixed;left:0;top:0;width:${S}px;height:${S}px;background:var(--bg);z-index:100;padding:34px 40px;box-sizing:border-box;display:grid;grid-template-rows:auto 1fr;gap:14px;overflow:hidden`;
          const head = document.createElement('div');
          head.innerHTML = `<div style="font:800 34px/1.1 var(--f-display);color:var(--ink)">How many people live near the station?</div>
            <div style="font:400 20px/1.4 var(--f-display);color:var(--ink-2);margin-top:8px">${title} · residents within <b id="gifR" style="color:var(--ink)">20 km</b> of each stop</div>`;
          const wrap = document.createElement('div');
          wrap.style.cssText = 'position:relative;overflow:hidden;background:var(--surface);border:1px solid var(--rule);border-radius:12px';
          const cmp = document.querySelector('#cmp');
          cmp.style.cssText = 'width:1000px;min-width:0;transform-origin:top left;position:absolute;left:0;top:0;padding:14px';
          wrap.append(cmp); box.append(head, wrap); document.body.append(box);
          window.__fit = () => { const s = Math.min(wrap.clientWidth / cmp.scrollWidth, wrap.clientHeight / cmp.scrollHeight);
            cmp.style.transform = `scale(${s})`; cmp.style.left = ((wrap.clientWidth - cmp.scrollWidth * s) / 2) + 'px'; };
        }""", [S, f"{short(names[0])} vs {short(names[1])}"])
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
    ap = argparse.ArgumentParser()
    ap.add_argument("left", nargs="?", default="ca"); ap.add_argument("right", nargs="?", default="es")
    ap.add_argument("--slide", type=int, help="km to slide the shorter route (default: 116 for ca/es, else 0)")
    ap.add_argument("--flip-left", action="store_true"); ap.add_argument("--flip-right", action="store_true")
    ap.add_argument("--mp4", action="store_true", help="also write a 1080×1080 MP4 for Instagram to out/")
    a = ap.parse_args()
    if a.slide is None:
        a.slide = 116 if (a.left, a.right) == ("ca", "es") else 0
    srv = serve()
    out = os.path.join(DOCS, f"compare_{a.left}_{a.right}_radius.gif")
    with tempfile.TemporaryDirectory() as frames:
        asyncio.run(capture(f"http://127.0.0.1:{srv.server_address[1]}/", frames, a))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "%04d.png"),
                        "-vf", f"scale={OUT_PX}:{OUT_PX}:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];"
                               "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                        "-loop", "0", out], check=True)
        if a.mp4:   # full 1080 px frames, played twice (~19 s), 30 fps, silent AAC track for maximum app compatibility
            os.makedirs(os.path.join(os.path.dirname(DOCS), "out"), exist_ok=True)
            mp4 = os.path.join(os.path.dirname(DOCS), "out", f"compare_{a.left}_{a.right}_radius.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "1", "-framerate", str(FPS),
                            "-i", os.path.join(frames, "%04d.png"), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-vf", f"scale={S}:{S}:flags=lanczos,fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                            "-crf", "18", "-profile:v", "high", "-level", "4.0", "-c:a", "aac", "-b:a", "64k", "-shortest",
                            "-movflags", "+faststart", mp4], check=True)
            print("wrote", os.path.relpath(mp4))
    srv.shutdown()
    print("wrote", os.path.relpath(out))


if __name__ == "__main__":
    main()
