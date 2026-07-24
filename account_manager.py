#!/usr/bin/env python3
"""
Account Management Module for TGMSES
Handles: Config loading/saving, Account CRUD operations, Voice & Translation helpers
"""

import os
import json
import time
import uuid
import sys
import logging
import tempfile
import io

log = logging.getLogger("TGMSES")

CONFIG_PATH = "config.json"
MESSAGE_MAP_PATH = "message_map.json"

# Optional features detection
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    VOICE_SUPPORT = True
except ImportError:
    VOICE_SUPPORT = False

try:
    from deep_translator import GoogleTranslator
    TRANSLATE_SUPPORT = True
except ImportError:
    TRANSLATE_SUPPORT = False

def format_account_session_name(account_name):
    """Convert account name to session filename (e.g., 'My Account' -> 'session_my_account')"""
    return f"session_{account_name.lower().replace(' ', '_')}"

def ask_int(prompt):
    """Prompt user for an integer input"""
    while True:
        val = input(prompt).strip()
        if val.isdigit():
            return int(val)
        print("❌ Please enter numbers only.")

def ask_nonempty(prompt):
    """Prompt user for a non-empty string"""
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("❌ Cannot be empty. Try again.")

def load_or_create_config():
    """Load config if exists, otherwise create new one with user input"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            log.info("Configuration loaded from config.json")
            return config
        except Exception as e:
            log.error(f"Config file corrupted: {e}")
            print(f"❌ Config file corrupted. Please delete {CONFIG_PATH} and run again.")
            sys.exit(1)

    print("\n🛠️  First Time Setup Required\n")
    api_id = ask_int("[?] Enter API ID (from my.telegram.org): ")
    api_hash = ask_nonempty("[?] Enter API Hash: ")
    bot_token = ask_nonempty("[?] Enter Bot Token (from @BotFather): ")
    owner_id = ask_int("[?] Enter Your User ID: ")

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "bot_token": bot_token,
        "owner_id": owner_id,
        "accounts": [],
        "settings": {
            "keywords": [],
            "keywords_enabled": False,
            "transcribe_voice": False,
            "voice_lang": "en-US",
            "translate_target": None,
            "translate_enabled": False
        }
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("\n✅ Configuration saved to config.json\n")
    return config

def save_config(config):
    """Save config to file"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_message_map():
    """Load message mapping (bot message ID -> account/chat info)"""
    try:
        with open(MESSAGE_MAP_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def save_message_map(m):
    """Save message mapping to file"""
    with open(MESSAGE_MAP_PATH, "w") as f:
        json.dump(m, f)

# Account Management Functions
def add_account_to_config(config, name, phone):
    """Add a new account to the config"""
    account = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
        "session": format_account_session_name(name),
        "active": True,
        "added_date": time.strftime("%Y-%m-%d")
    }
    config["accounts"].append(account)
    save_config(config)
    return account

def remove_account_from_config(config, account_id):
    """Remove an account from the config"""
    config["accounts"] = [a for a in config["accounts"] if a["id"] != account_id]
    save_config(config)

def toggle_account_active(config, account_id):
    """Toggle account active/inactive status"""
    for acc in config["accounts"]:
        if acc["id"] == account_id:
            acc["active"] = not acc["active"]
            save_config(config)
            return acc
    return None

def edit_account_name(config, account_id, new_name):
    """Edit account name and update session filename"""
    for acc in config["accounts"]:
        if acc["id"] == account_id:
            acc["name"] = new_name
            acc["session"] = format_account_session_name(new_name)
            save_config(config)
            return acc
    return None

def matches_keyword(text, keywords):
    """Check if text contains any keyword (case-insensitive)"""
    if not keywords or not text:
        return False
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)

async def transcribe_voice(event, lang):
    """Convert voice message to text using Google Speech Recognition"""
    if not VOICE_SUPPORT:
        return None
    try:
        data = await event.download_media(file=bytes)
        with tempfile.TemporaryDirectory() as td:
            ogg_path = os.path.join(td, "voice.ogg")
            wav_path = os.path.join(td, "voice.wav")
            with open(ogg_path, "wb") as f:
                f.write(data)
            AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            return recognizer.recognize_google(audio, language=lang)
    except sr.UnknownValueError:
        return "(Voice could not be understood)"
    except Exception as e:
        log.warning(f"Voice transcription failed: {e}")
        return None

def translate_text(text, target):
    """Translate text to target language using deep-translator"""
    if not TRANSLATE_SUPPORT or not target or not text:
        return None
    try:
        translated = GoogleTranslator(source="auto", target=target).translate(text)
        if translated and translated.strip().lower() != text.strip().lower():
            return translated
        return None
    except Exception as e:
        log.warning(f"Translation failed: {e}")
        return None

async def relay_media(event, dest_client, dest_chat_id, caption=None):
    """Forward media from one account to another"""
    msg = event.message
    data = await event.download_media(file=bytes)
    bio = io.BytesIO(data)
    
    ext = ""
    if msg.file and msg.file.ext:
        ext = msg.file.ext
    bio.name = f"file{ext}"
    
    kwargs = {}
    if caption:
        kwargs["caption"] = caption
    if msg.voice:
        kwargs["voice_note"] = True
    if msg.video_note:
        kwargs["video_note"] = True
    if msg.document and msg.document.attributes:
        kwargs["attributes"] = msg.document.attributes
    
    return await dest_client.send_file(dest_chat_id, bio, **kwargs)
