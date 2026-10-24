"""Capturas da interface v6. Uso: servidor rodando; python tools_screenshots_v6.py [url]"""
import asyncio, sys
from playwright.async_api import async_playwright
URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000") + "/v6/"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = await b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: print("ERRO:", e)); pg.on("console", lambda m: m.type == "error" and print("console:", m.text))
        await pg.goto(URL); await pg.wait_for_timeout(9000)
        await pg.screenshot(path="screenshots/v6_03_notebook.png")
        await pg.evaluate("document.getElementById('tts').checked=false; jarvis.modo('esfera'); jarvis.falar('Olá Bruno, sistemas online e prontos para trabalhar com você hoje.')")
        await pg.wait_for_timeout(1200); await pg.screenshot(path="screenshots/v6_01_esfera_falando.png")
        await pg.evaluate("jarvis.agir('tela')"); await pg.wait_for_timeout(2500)
        await pg.screenshot(path="screenshots/v6_02_tela_grande.png")
        await pg.evaluate("document.querySelector('[data-agir=direto]').click()"); await pg.wait_for_timeout(800)
        await pg.screenshot(path="screenshots/v6_04_modo_direto.png")
        await b.close()
asyncio.run(main())
