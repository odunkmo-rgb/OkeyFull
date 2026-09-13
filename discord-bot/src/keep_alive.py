import os
import asyncio
from aiohttp import web

# Railway injects PORT at runtime. KEEPALIVE_PORT remains available as a
# local override when running the bot outside Railway.
PORT = int(os.environ.get("PORT") or os.environ.get("KEEPALIVE_PORT", "8080"))

async def health(request):
    return web.Response(text="✅ Kahvehane Okey Botu çalışıyor!", status=200)

async def start_keep_alive():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Keep-alive sunucusu başlatıldı → port {PORT}")
