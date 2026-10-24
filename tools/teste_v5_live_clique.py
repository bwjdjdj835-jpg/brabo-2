import asyncio, json, urllib.request, mss, mss.tools
from playwright.async_api import async_playwright
S='/workspace/jarvis/screenshots/'
def api(p,d=None):
    r=urllib.request.Request('http://localhost:8010'+p,data=json.dumps(d).encode() if d is not None else None,headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(r).read())
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        pg=await b.new_page(viewport={'width':1600,'height':900})
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        pg.on('console', lambda m: print('console:',m.text) if m.type=='error' else None)
        await pg.goto('http://localhost:8010'); await pg.wait_for_timeout(15000)
        await pg.screenshot(path=S+'v5_01_LIVE_camera5D_padrao.png')
        for i,v in [(2,'medio'),(3,'close'),(4,'ombro')]:
            await pg.click(f'.vistas button[data-v={v}]'); await pg.wait_for_timeout(4000)
            await pg.screenshot(path=S+f'v5_0{i}_{v}.png')
        await pg.click('.vistas button[data-v=live5d]'); await pg.wait_for_timeout(4000)
        await pg.click('#togControle'); await pg.wait_for_timeout(1500)
        print('status', api('/api/log')['ligado'])
        x,y=await pg.evaluate('jarvis.cena.pontoNaJanela(317/1024,159/576)'); print('alvo',x,y)
        await pg.mouse.move(x,y); await pg.wait_for_timeout(300); await pg.mouse.down(); await pg.mouse.up()
        await pg.wait_for_timeout(500); await pg.screenshot(path=S+'v5_05_live_ryker_clicando.png')
        await pg.wait_for_timeout(3000)
        await pg.screenshot(path=S+'v5_06_live_clique_refletido.png')
        with mss.mss() as s: i=s.grab(s.monitors[1]); mss.tools.to_png(i.rgb,i.size,output=S+'v5_07_desktop_real_x7_apos_clique.png')

        await pg.click('#parar'); await pg.wait_for_timeout(1500)
        print(api('/api/log'))
        await pg.screenshot(path=S+'v5_08_parado.png')
        await b.close()
asyncio.run(main())
