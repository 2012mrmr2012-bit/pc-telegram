# -*- coding: utf-8 -*-
"""
bot.py - بوت تليجرام للتحكم عن بعد في الأجهزة المربوطة.
شغّله بـ: python bot.py (لازم api.py يكون شغال في الخلفية كمان لأن الـ Agent بيكلمه).

قبل التشغيل:
  1) حط التوكن بتاع البوت في متغير البيئة BOT_TOKEN
  2) شغّل uvicorn api:app --host 0.0.0.0 --port 8000 (في تيرمنال منفصل)
"""
import asyncio
import os
import time
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

import db

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8817646680:AAGfUAyOyHvxdhxPXlLDVe9p8pkCUqWrGUM")
POLL_WAIT_SECONDS = 8  # أد ايه البوت يستنى نتيجة الأمر قبل ما يقول "بينفذ..."

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db.init_db()

# الكيبورد الثابت في الأسفل — أزرار سريعة للأوامر الأكثر استخداماً
MAIN_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📸 لقطة شاشة"),
            KeyboardButton(text="📊 حالة الجهاز"),
        ],
        [
            KeyboardButton(text="🌑 إطفاء الشاشة"),
            KeyboardButton(text="☀️ تشغيل الشاشة"),
        ],
        [
            KeyboardButton(text="🔇 كتم الصوت"),
            KeyboardButton(text="🔔 فك الكتم"),
        ],
        [
            KeyboardButton(text="🔒 قفل الجهاز"),
            KeyboardButton(text="💤 وضع السكون"),
        ],
        [
            KeyboardButton(text="📱 لوحة التحكم الكاملة"),
        ],
    ],
    resize_keyboard=True,
)

def get_main_menu_keyboard():
    """لوحة التحكم الرئيسية بالعربي (Inline Buttons)."""
    kb = [
        [
            InlineKeyboardButton(text="📊 حالة الجهاز", callback_data="btn_status"),
            InlineKeyboardButton(text="🔋 البطارية", callback_data="btn_battery"),
        ],
        [
            InlineKeyboardButton(text="📸 لقطة شاشة", callback_data="btn_screenshot"),
            InlineKeyboardButton(text="⚡ العمليات والرام", callback_data="btn_processes"),
        ],
        [
            InlineKeyboardButton(text="☀️ ضبط السطوع", callback_data="menu_brightness"),
            InlineKeyboardButton(text="🔊 مستوى الصوت", callback_data="menu_volume"),
        ],
        [
            InlineKeyboardButton(text="🔇 كتم الصوت", callback_data="btn_mute"),
            InlineKeyboardButton(text="🔔 تشغيل الصوت", callback_data="btn_unmute"),
        ],
        [
            InlineKeyboardButton(text="🔄 مدخل الشاشة (DP / HDMI)", callback_data="menu_switch"),
        ],
        [
            InlineKeyboardButton(text="🌑 إطفاء / سكون الشاشة", callback_data="btn_monitoroff"),
            InlineKeyboardButton(text="☀️ تشغيل الشاشة", callback_data="btn_monitoron"),
        ],
        [
            InlineKeyboardButton(text="🌐 الشبكة (IP)", callback_data="btn_network"),
            InlineKeyboardButton(text="📡 تفاصيل الشبكة", callback_data="btn_netinfo"),
        ],
        [
            InlineKeyboardButton(text="📶 تشغيل الواي فاي", callback_data="btn_wifi_on"),
            InlineKeyboardButton(text="📵 إيقاف الواي فاي", callback_data="btn_wifi_off"),
        ],
        [
            InlineKeyboardButton(text="🧹 تفريغ DNS", callback_data="btn_flushdns"),
            InlineKeyboardButton(text="🔒 قفل الكمبيوتر", callback_data="btn_lock"),
        ],
        [
            InlineKeyboardButton(text="💤 وضع السكون (Sleep)", callback_data="btn_sleep"),
            InlineKeyboardButton(text="🛌 وضع الإسبات (Hibernate)", callback_data="btn_hibernate"),
        ],
        [
            InlineKeyboardButton(text="🔄 إعادة التشغيل", callback_data="btn_restart"),
            InlineKeyboardButton(text="🛑 إطفاء الجهاز", callback_data="btn_shutdown"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9):
    """إرسال حزمة Magic Packet لتشغيل الكمبيوتر عن بعد."""
    import socket
    clean_mac = mac_address.replace(":", "").replace("-", "")
    if len(clean_mac) != 12:
        raise ValueError("Invalid MAC address")
    magic_payload = bytes.fromhex("FF" * 6 + clean_mac * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_payload, (broadcast_ip, port))



def get_slider_keyboard(action_prefix: str, current_title: str):
    """لوحة أزرار اختيار النسبة المئوية من 0 لـ 100 مع زر رجوع."""
    kb = [
        [
            InlineKeyboardButton(text="0%", callback_data=f"{action_prefix}_0"),
            InlineKeyboardButton(text="10%", callback_data=f"{action_prefix}_10"),
            InlineKeyboardButton(text="20%", callback_data=f"{action_prefix}_20"),
            InlineKeyboardButton(text="30%", callback_data=f"{action_prefix}_30"),
        ],
        [
            InlineKeyboardButton(text="40%", callback_data=f"{action_prefix}_40"),
            InlineKeyboardButton(text="50%", callback_data=f"{action_prefix}_50"),
            InlineKeyboardButton(text="60%", callback_data=f"{action_prefix}_60"),
            InlineKeyboardButton(text="70%", callback_data=f"{action_prefix}_70"),
        ],
        [
            InlineKeyboardButton(text="80%", callback_data=f"{action_prefix}_80"),
            InlineKeyboardButton(text="90%", callback_data=f"{action_prefix}_90"),
            InlineKeyboardButton(text="100%", callback_data=f"{action_prefix}_100"),
        ],
        [
            InlineKeyboardButton(text="⬅️ رجوع للقائمة الرئيسية", callback_data="menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_switch_keyboard():
    """لوحة اختيار مدخل الشاشة DP أو HDMI."""
    kb = [
        [
            InlineKeyboardButton(text="🖥️ DisplayPort (DP)", callback_data="switch_dp"),
            InlineKeyboardButton(text="📺 HDMI", callback_data="switch_hdmi"),
        ],
        [
            InlineKeyboardButton(text="⬅️ رجوع للقائمة الرئيسية", callback_data="menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# الأوامر المسموح تنفيذها عن طريق /run فقط (whitelist أمني)
ALLOWED_SHELL_COMMANDS = {
    "dir", "ls", "whoami", "hostname", "ipconfig", "ifconfig",
    "systeminfo", "tasklist", "ps",
}


def require_paired(chat_id: int):
    user = db.get_user_by_chat(chat_id)
    if not user:
        return None
    return user


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = require_paired(message.chat.id)
    if user:
        await message.answer(
            f"✅ جهازك مربوط بالفعل: *{user['device_name']}*\n"
            "اضغط على أي زر في لوحة التحكم للتحكم المباشر 👇",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await message.answer("💡 تم تفعيل زرار القائمة الدائم في الكيبورد بالأسفل.", reply_markup=MAIN_REPLY_KEYBOARD)
        return

    code = db.create_pairing_code(message.chat.id, ttl_seconds=300)
    await message.answer(
        "🔗 *خطوات الربط:*\n"
        "1. شغّل برنامج `run_agent.bat` على الكمبيوتر\n"
        "2. لما يطلب منك كود، اكتب الكود ده:\n\n"
        f"`{code}`\n\n"
        "⏳ الكود صالح لمدة 5 دقايق بس.",
        parse_mode="Markdown",
    )


@dp.message(F.text == "📱 لوحة التحكم الكاملة")
@dp.message(F.text == "📱 لوحة التحكم بالأزرار")
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    user = require_paired(message.chat.id)
    if not user:
        await message.answer("❌ مفيش جهاز مربوط. ابعت /start للربط أولاً.")
        return
    await message.answer(
        "🎛️ *قائمة الأوامر والتحكم بالعربي:*\nاختر الأمر المطلوب تنفيذه مباشرة 👇",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


# ─── أزرار الكيبورد الثابت في الأسفل ────────────────────────────────────────

@dp.message(F.text == "📸 لقطة شاشة")
async def kb_screenshot(message: Message):
    await send_command_and_wait(message, "screenshot")

@dp.message(F.text == "📊 حالة الجهاز")
async def kb_status(message: Message):
    await send_command_and_wait(message, "status")

@dp.message(F.text == "🌑 إطفاء الشاشة")
async def kb_monitoroff(message: Message):
    await send_command_and_wait(message, "monitoroff")

@dp.message(F.text == "☀️ تشغيل الشاشة")
async def kb_monitoron(message: Message):
    await send_command_and_wait(message, "monitoron")

@dp.message(F.text == "🔇 كتم الصوت")
async def kb_mute(message: Message):
    await send_command_and_wait(message, "mute")

@dp.message(F.text == "🔔 فك الكتم")
async def kb_unmute(message: Message):
    await send_command_and_wait(message, "unmute")

@dp.message(F.text == "🔒 قفل الجهاز")
async def kb_lock(message: Message):
    await send_command_and_wait(message, "lock")

@dp.message(F.text == "💤 وضع السكون")
async def kb_sleep(message: Message):
    await send_command_and_wait(message, "sleep")




@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 *الأوامر المتاحة بعد الربط:*\n\n"
        "🖥️ *معلومات وحالة الجهاز*\n"
        "/status - حالة الجهاز (CPU/RAM/تخزين)\n"
        "/network - عناوين IP للشبكة\n"
        "/netinfo - تفاصيل الشبكة الكاملة\n"
        "/battery - نسبة البطارية\n"
        "/processes - أكثر العمليات استهلاكًا للرام\n\n"
        "⚡ *الطاقة وإدارة الجهاز*\n"
        "/lock - قفل الجهاز\n"
        "/shutdown - إطفاء الجهاز\n"
        "/restart - إعادة تشغيل الجهاز\n"
        "/sleep - وضع السكون\n"
        "/hibernate - وضع الإسبات\n\n"
        "🖥️ *الشاشة والعرض*\n"
        "/screenshot - لقطة شاشة\n"
        "/monitoroff - إطفاء الشاشة\n"
        "/brightness <0-100> - ضبط السطوع\n"
        "/switch <hdmi|dp> - تحويل مدخل الشاشة (HDMI / DisplayPort)\n"
        "/displaymode <extend|clone|internal|external> - وضع الشاشات\n\n"
        "🔊 *الصوت*\n"
        "/mute - كتم الصوت\n"
        "/unmute - إلغاء كتم الصوت\n"
        "/volume <0-100> - ضبط مستوى الصوت\n\n"
        "🌐 *الشبكة*\n"
        "/wifi on|off - تشغيل/إيقاف الواي فاي\n"
        "/flushdns - تفريغ ذاكرة الـ DNS\n\n"
        "⚙️ *متفرقات*\n"
        "/kill <اسم العملية> - إنهاء عملية\n"
        "/run <أمر> - تنفيذ أمر من قايمة محدودة مسموحة\n"
        "/unpair - فك الربط مع الجهاز",
        parse_mode="Markdown",
    )


@dp.message(Command("unpair"))
async def cmd_unpair(message: Message):
    db.unpair(message.chat.id)
    await message.answer("🔓 تم فك الربط مع الجهاز.")


POLL_WAIT_SECONDS = 15  # أد ايه البوت يستنى نتيجة الأمر مباشرة


async def _watch_delayed_command(chat_id: int, cmd_id: int):
    """مراقبة النتيجة في الخلفية لو اتأخرت وإرسالها أول ما تخلص."""
    for _ in range(60):  # انتظر حتى دقيقة
        await asyncio.sleep(1)
        row = db.get_command(cmd_id)
        if row and row["status"] != "pending":
            if row["status"] == "done":
                await bot.send_message(chat_id, f"✅ النتيجة وصلت:\n{row['result']}")
            else:
                await bot.send_message(chat_id, f"⚠️ حصل خطأ:\n{row['result']}")
            return


async def send_command_and_wait(message: Message, command: str, args: dict = None):
    user = require_paired(message.chat.id)
    if not user:
        await message.answer("❌ مفيش جهاز مربوط. ابعت /start عشان تربط جهاز الأول.")
        return

    cmd_id = db.push_command(user["device_id"], command, args)
    wait_msg = await message.answer("⏳ جاري التنفيذ على الجهاز...")

    # نستنى النتيجة لفترة مناسبة
    deadline = time.time() + POLL_WAIT_SECONDS
    while time.time() < deadline:
        row = db.get_command(cmd_id)
        if row["status"] != "pending":
            if row["status"] == "done":
                await wait_msg.edit_text(f"✅ النتيجة:\n{row['result']}")
            else:
                await wait_msg.edit_text(f"⚠️ حصل خطأ:\n{row['result']}")
            return
        await asyncio.sleep(0.5)

    # الجهاز مش بيرد = مش مربوط أو مش شغال
    await wait_msg.edit_text(
        "🔴 الجهاز مش بيرد!\n\n"
        "• تأكد إن برنامج الـ Agent شغال على الكمبيوتر\n"
        "• أو شغّل `run_agent.bat` على الجهاز\n\n"
        "📡 هيوصلك الرد تلقائياً لو الجهاز اتصل."
    )
    asyncio.create_task(_watch_delayed_command(message.chat.id, cmd_id))



@dp.message(Command("status"))
async def cmd_status(message: Message):
    await send_command_and_wait(message, "status")


@dp.message(Command("screenshot"))
async def cmd_screenshot(message: Message):
    await send_command_and_wait(message, "screenshot")


@dp.message(Command("lock"))
async def cmd_lock(message: Message):
    await send_command_and_wait(message, "lock")


@dp.message(Command("shutdown"))
async def cmd_shutdown(message: Message):
    await send_command_and_wait(message, "shutdown")


@dp.message(Command("restart"))
async def cmd_restart(message: Message):
    await send_command_and_wait(message, "restart")


@dp.message(Command("run"))
async def cmd_run(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("استخدم: /run <أمر>\nمثال: /run whoami")
        return
    cmd_text = parts[1].strip()
    first_word = cmd_text.split()[0].lower()
    if first_word not in ALLOWED_SHELL_COMMANDS:
        await message.answer(
            "🚫 الأمر ده مش مسموح لأسباب أمنية.\n"
            f"الأوامر المسموحة: {', '.join(sorted(ALLOWED_SHELL_COMMANDS))}"
        )
        return
    await send_command_and_wait(message, "run", {"cmd": cmd_text})


# ---------- أوامر جديدة ----------

@dp.message(Command("netinfo"))
async def cmd_netinfo(message: Message):
    await send_command_and_wait(message, "netinfo")


@dp.message(Command("hibernate"))
async def cmd_hibernate(message: Message):
    await send_command_and_wait(message, "hibernate")


@dp.message(Command("monitoroff"))
async def cmd_monitoroff(message: Message):
    await send_command_and_wait(message, "monitoroff")


@dp.message(Command("brightness"))
async def cmd_brightness(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("استخدم: /brightness <0-100>\nمثال: /brightness 70")
        return
    await send_command_and_wait(message, "brightness", {"level": int(parts[1].strip())})


@dp.message(Command("switch"))
async def cmd_switch(message: Message):
    parts = message.text.split(maxsplit=1)
    valid = ("dp", "displayport", "hdmi", "hdmi1", "hdmi2")
    if len(parts) < 2 or parts[1].strip().lower() not in valid:
        await message.answer(
            "استخدم: /switch <dp | hdmi>\n"
            "مثال للتحويل لـ HDMI:\n`/switch hdmi`\n"
            "مثال للتحويل لـ DisplayPort:\n`/switch dp`",
            parse_mode="Markdown"
        )
        return
    await send_command_and_wait(message, "switch", {"input": parts[1].strip().lower()})


@dp.message(Command("displaymode"))

async def cmd_displaymode(message: Message):
    parts = message.text.split(maxsplit=1)
    valid = ("extend", "clone", "internal", "external")
    if len(parts) < 2 or parts[1].strip().lower() not in valid:
        await message.answer(
            f"استخدم: /displaymode <{' | '.join(valid)}>\n"
            "مثال: /displaymode extend"
        )
        return
    await send_command_and_wait(message, "displaymode", {"mode": parts[1].strip().lower()})


@dp.message(Command("mute"))
async def cmd_mute(message: Message):
    await send_command_and_wait(message, "mute")


@dp.message(Command("unmute"))
async def cmd_unmute(message: Message):
    await send_command_and_wait(message, "unmute")


@dp.message(Command("volume"))
async def cmd_volume(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("استخدم: /volume <0-100>\nمثال: /volume 50")
        return
    await send_command_and_wait(message, "volume", {"level": int(parts[1].strip())})


@dp.message(Command("wifi"))
async def cmd_wifi(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip().lower() not in ("on", "off"):
        await message.answer("استخدم: /wifi on أو /wifi off")
        return
    await send_command_and_wait(message, "wifi", {"state": parts[1].strip().lower()})


@dp.message(Command("flushdns"))
async def cmd_flushdns(message: Message):
    await send_command_and_wait(message, "flushdns")


@dp.message(Command("battery"))
async def cmd_battery(message: Message):
    await send_command_and_wait(message, "battery")


@dp.message(Command("network"))
async def cmd_network(message: Message):
    await send_command_and_wait(message, "network")


@dp.message(Command("processes"))
async def cmd_processes(message: Message):
    await send_command_and_wait(message, "processes")


@dp.message(Command("sleep"))
async def cmd_sleep(message: Message):
    await send_command_and_wait(message, "sleep")


@dp.message(Command("kill"))
async def cmd_kill(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("استخدم: /kill <اسم العملية أو PID>\nمثال: /kill notepad.exe")
        return
    await send_command_and_wait(message, "kill", {"name": parts[1].strip()})


@dp.message(Command("ping"))
@dp.message(Command("say"))
async def cmd_say(message: Message):
    """أمر لاختبار استجابة الكمبيوتر بالإنجليزية فوراً."""
    await send_command_and_wait(message, "say")



# ─── معالجة الضغط على أزرار لوحة التحكم (Callback Queries) ──────────────

@dp.callback_query()
async def handle_callback_buttons(callback: CallbackQuery):
    data = callback.data
    user = require_paired(callback.message.chat.id)
    if not user:
        await callback.answer("❌ لا يوجد جهاز مربوط!", show_alert=True)
        return

    # 1. التنقل بين القوائم
    if data == "menu_main":
        await callback.message.edit_text(
            "🎛️ *قائمة الأوامر والتحكم بالعربي:*\nاختر الأمر المطلوب تنفيذه مباشرة 👇",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return

    elif data == "menu_brightness":
        await callback.message.edit_text(
            "☀️ *اختر نسبة سطوع الشاشة المطلوبة:*",
            parse_mode="Markdown",
            reply_markup=get_slider_keyboard("set_brightness", "السطوع")
        )
        await callback.answer()
        return

    elif data == "menu_volume":
        await callback.message.edit_text(
            "🔊 *اختر مستوى صوت النظام المطلوب:*",
            parse_mode="Markdown",
            reply_markup=get_slider_keyboard("set_volume", "الصوت")
        )
        await callback.answer()
        return

    elif data == "menu_switch":
        await callback.message.edit_text(
            "🔄 *اختر مدخل الشاشة المطلوب التحويل إليه:*",
            parse_mode="Markdown",
            reply_markup=get_switch_keyboard()
        )
        await callback.answer()
        return

    # 2. تنفيذ نسب السطوع
    elif data.startswith("set_brightness_"):
        val = int(data.split("_")[-1])
        await callback.answer(f"جاري ضبط السطوع على {val}%...")
        await send_command_and_wait(callback.message, "brightness", {"level": val})
        return

    # 3. تنفيذ نسب الصوت
    elif data.startswith("set_volume_"):
        val = int(data.split("_")[-1])
        await callback.answer(f"جاري ضبط الصوت على {val}%...")
        await send_command_and_wait(callback.message, "volume", {"level": val})
        return

    # 4. تنفيذ تحويل المدخل
    elif data == "switch_dp":
        await callback.answer("جاري التحويل لـ DisplayPort...")
        await send_command_and_wait(callback.message, "switch", {"input": "dp"})
        return

    elif data == "switch_hdmi":
        await callback.answer("جاري التحويل لـ HDMI...")
        await send_command_and_wait(callback.message, "switch", {"input": "hdmi"})
        return

    elif data == "btn_wakeonlan":
        # جهاز المستخدم
        mac = "3c:52:82:50:dd:0b"
        try:
            send_wake_on_lan(mac)
            await callback.answer("⚡ تم إرسال حزمة التشغيل Magic Packet!", show_alert=True)
            await callback.message.answer(
                f"⚡ *تم إرسال إشارة التشغيل (Wake on LAN)!*\n"
                f"📡 الجهاز المستهدف MAC: `{mac}`\n"
                f"إذا كان كارت الشبكة والـ BIOS يدعمان WoL، سيبدأ الكمبيوتر بالعمل الآن.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"❌ خطأ أثناء الإرسال: {e}", show_alert=True)
        return


    # 5. الأوامر المباشرة من الأزرار
    cmd_map = {
        "btn_status": ("status", None),
        "btn_battery": ("battery", None),
        "btn_screenshot": ("screenshot", None),
        "btn_processes": ("processes", None),
        "btn_mute": ("mute", None),
        "btn_unmute": ("unmute", None),
        "btn_monitoroff": ("monitoroff", None),
        "btn_monitoron": ("monitoron", None),
        "btn_network": ("network", None),
        "btn_netinfo": ("netinfo", None),
        "btn_wifi_on": ("wifi", {"state": "on"}),
        "btn_wifi_off": ("wifi", {"state": "off"}),
        "btn_flushdns": ("flushdns", None),
        "btn_lock": ("lock", None),
        "btn_sleep": ("sleep", None),
        "btn_hibernate": ("hibernate", None),
        "btn_restart": ("restart", None),
        "btn_shutdown": ("shutdown", None),
    }

    if data in cmd_map:
        cmd, args = cmd_map[data]
        await callback.answer("⏳ جاري التنفيذ...")
        await send_command_and_wait(callback.message, cmd, args)
        return

    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

