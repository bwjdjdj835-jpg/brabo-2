"""Gera capturas da interface v3 (requer: pip install playwright && playwright install chromium; servidor rodando)."""
import asyncio, sys
from playwright.async_api import async_playwright
URL = "http://127.0.0.1:8000"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = await b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("console", lambda m: print("console:", m.text)); pg.on("pageerror", lambda e: print("ERRO:", e))
        await pg.goto(URL); await pg.wait_for_timeout(12000)
        await pg.evaluate("document.getElementById('tts').checked=false; jarvis.enviar('oi Jarvis')")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path="screenshots/v3_01_live_webcam_falando.png")
        await pg.evaluate("document.querySelector('[data-v=orbita]').click(); jarvis.enviar('status do sistema')"); await pg.wait_for_timeout(2500)
        await pg.screenshot(path="screenshots/v3_02_orbita_360.png")
        await pg.evaluate("document.querySelector('[data-v=quarto]').click()"); await pg.wait_for_timeout(5000)
        await pg.screenshot(path="screenshots/v3_03_quarto.png")
        await pg.evaluate("document.querySelector('[data-v=rosto]').click(); jarvis.enviar('conte uma piada')"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path="screenshots/v3_04_rosto.png")
        await b.close()
asyncio.run(main())
