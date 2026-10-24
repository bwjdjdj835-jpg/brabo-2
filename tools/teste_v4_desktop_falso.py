import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=False,args=['--window-position=0,0','--window-size=1920,1080','--kiosk'])
        pg=await b.new_page(no_viewport=True); await pg.goto('file://' + __import__('os').path.abspath(__import__('os').path.join(__import__('os').path.dirname(__file__),'desktop.html')) + '')
        while True: await asyncio.sleep(60)
asyncio.run(main())
