# -*- coding: utf-8 -*-
"""
start_server.py
ملف التشغيل السحابي - بيشغل خادم الـ API وبوت تليجرام مع بعض في عملية واحدة
عشان الاستضافات السحابية (Render, Railway, VPS) تشغل كل حاجة بملف واحد.
"""
import asyncio
import os
import sys
import uvicorn

# التأكد من مجلد السيرفر
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import app
from bot import dp, bot
import db

async def run_api_server():
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def run_bot_polling():
    await asyncio.sleep(2)
    print("🤖 Telegram Bot is starting polling...")
    await dp.start_polling(bot)

async def main():
    db.init_db()
    print("🚀 Initializing Cloud Server (API + Telegram Bot)...")
    await asyncio.gather(
        run_api_server(),
        run_bot_polling()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Server stopped.")
