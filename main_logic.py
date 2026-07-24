#!/usr/bin/env python3
"""
Main Bot Logic Module for TGMSES
Handles: Bot initialization, Menu UI, Message Forwarding, Reply Logic
"""

import os
import io
import logging
import asyncio
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, AuthKeyUnregisteredError

log = logging.getLogger("TGMSES")

# Import functions from account_manager
from account_manager import (
    load_message_map, save_message_map, 
    relay_media, transcribe_voice, translate_text, matches_keyword,
    add_account_to_config, remove_account_from_config, 
    toggle_account_active, edit_account_name
)

# Global variables
user_clients = {}
current_add_account_flow = {}

async def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

# --- Menu Display Functions ---

async def show_main_menu(bot, user_id, config, existing_msg_id=None):
    buttons = [
        [Button.inline("➕ Add Account", b"add_account")],
        [Button.inline("📋 Manage Accounts", b"manage_accounts")],
        [Button.inline("⚙️ Settings", b"settings")],
        [Button.inline("📊 Status", b"status")],
        [Button.inline("❌ Stop Hub", b"stop_hub")]
    ]
    text = "🏠 MAIN MENU"
    if existing_msg_id:
        try: await bot.edit_message(user_id, existing_msg_id, text, buttons=buttons)
        except: await bot.send_message(user_id, text, buttons=buttons)
    else: await bot.send_message(user_id, text, buttons=buttons)

async def show_manage_accounts(bot, user_id, config, existing_msg_id=None):
    buttons = []
    for i, acc in enumerate(config["accounts"]):
        status = "✅" if acc["active"] else "⭕"
        buttons.append([Button.inline(f"{i+1}️⃣ {acc['name']} ({status})", f"account_{acc['id']}".encode())])
    buttons.append([Button.inline("➕ Add New Account", b"add_account")])
    buttons.append([Button.inline("🔙 Back", b"main_menu")])
    
    text = "📋 MANAGE ACCOUNTS" if config["accounts"] else "📋 MANAGE ACCOUNTS\n\n❌ No accounts yet.\n➕ Add New Account"
    
    if existing_msg_id:
        try: await bot.edit_message(user_id, existing_msg_id, text, buttons=buttons)
        except: await bot.send_message(user_id, text, buttons=buttons)
    else: await bot.send_message(user_id, text, buttons=buttons)

async def show_account_options(bot, user_id, config, account_id, existing_msg_id=None):
    account = next((a for a in config["accounts"] if a["id"] == account_id), None)
    if not account: return
    status = "Active ✅" if account["active"] else "Inactive ⭕"
    toggle_btn = "🔄 Toggle to Inactive" if account["active"] else "🔄 Toggle to Active"
    
    buttons = [
        [Button.inline("✏️ Edit Name", f"edit_name_{account_id}".encode())],
        [Button.inline(toggle_btn, f"toggle_{account_id}".encode())],
        [Button.inline("🗑️ Remove Account", f"remove_{account_id}".encode())],
        [Button.inline("🔙 Back", b"manage_accounts")]
    ]
    text = f"""📌 {account['name']} - Options

📌 Status: {status}
📱 Phone: {account['phone']}
⏰ Added: {account['added_date']}"""
    
    if existing_msg_id:
        try: await bot.edit_message(user_id, existing_msg_id, text, buttons=buttons)
        except: await bot.send_message(user_id, text, buttons=buttons)
    else: await bot.send_message(user_id, text, buttons=buttons)

async def show_settings(bot, user_id, config, existing_msg_id=None):
    buttons = [
        [Button.inline("🔔 Keyword Alerts", b"settings_keywords")],
        [Button.inline("🎙️ Voice Transcription", b"settings_voice")],
        [Button.inline("🌐 Auto-translate", b"settings_translate")],
        [Button.inline("🔙 Back", b"main_menu")]
    ]
    text = "⚙️ SETTINGS"
    if existing_msg_id:
        try: await bot.edit_message(user_id, existing_msg_id, text, buttons=buttons)
        except: await bot.send_message(user_id, text, buttons=buttons)
    else: await bot.send_message(user_id, text, buttons=buttons)

async def show_status(bot, user_id, config, existing_msg_id=None):
    active_count = sum(1 for a in config["accounts"] if a["active"])
    total_count = len(config["accounts"])
    active_list = "\n".join([f"• {a['name']}" for a in config["accounts"] if a["active"]]) or "None"
    
    kw_status = "Enabled" if config["settings"]["keywords_enabled"] else "Disabled"
    vs_status = "Enabled" if config["settings"]["transcribe_voice"] else "Disabled"
    ts_status = "Enabled" if config["settings"]["translate_enabled"] else "Disabled"
    
    text = f"""📊 HUB STATUS

✅ Bot: Connected
📱 Accounts: {active_count} Active / {total_count} Total

Active Accounts:
{active_list}

Settings:
🔔 Keywords: {kw_status}
🎙️ Voice: {vs_status}
🌐 Translate: {ts_status}"""
    buttons = [[Button.inline("🔙 Back", b"main_menu")]]
    
    if existing_msg_id:
        try: await bot.edit_message(user_id, existing_msg_id, text, buttons=buttons)
        except: await bot.send_message(user_id, text, buttons=buttons)
    else: await bot.send_message(user_id, text, buttons=buttons)

# --- Main Bot Logic ---

async def run_bot(config):
    global user_clients
    api_id = config["api_id"]
    api_hash = config["api_hash"]
    owner_id = config["owner_id"]
    bot_token = config["bot_token"]
    message_map = load_message_map()

    # Init Bot
    bot = TelegramClient("bot_session", api_id, api_hash)
    await bot.start(bot_token=bot_token)
    log.info("✅ Bot connected")

    # Init User Clients
    user_clients = {}
    for acc in config["accounts"]:
        try:
            client = TelegramClient(acc["session"], api_id, api_hash)
            print(f"\nConnecting account: {acc['name']} ({acc['phone']})")
            await client.start(phone=acc["phone"])
            user_clients[acc["id"]] = client
            log.info(f"✅ Account connected: {acc['name']}")
        except Exception as e:
            log.error(f"Failed to connect {acc['name']}: {e}")

    print("\n✅ TGMSES is running. Press Ctrl+C to stop.")
    await show_main_menu(bot, owner_id, config)

    # --- Message Forwarding ---
    @bot.on(events.NewMessage(incoming=True))
    async def on_personal_message(event):
        acc_id = None
        for aid, client in user_clients.items():
            if client == event.client:
                acc_id = aid
                break
        if not acc_id: return
        
        account = next((a for a in config["accounts"] if a["id"] == acc_id), None)
        if not account or not account["active"]: return
        if not event.is_private: return

        sender = await event.get_sender()
        if getattr(sender, "bot", False): return

        full_name = f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip() or "Unknown"
        username = f"@{sender.username}" if getattr(sender, "username", None) else ""
        original_text = event.raw_text or ""
        text = original_text

        if event.message.voice and config["settings"]["transcribe_voice"]:
            transcript = await transcribe_voice(event, config["settings"]["voice_lang"])
            if transcript: text = f"{text}\n📝 {transcript}".strip()

        if config["settings"]["translate_enabled"] and config["settings"]["translate_target"]:
            translated = translate_text(text, config["settings"]["translate_target"])
            if translated: text = f"{text}\n🌐 {translated}"

        header = f"📨 {account['name']}\n👤 {full_name} {username}".strip()
        if matches_keyword(original_text, config["settings"]["keywords"]):
            header = f"🚨 KEYWORD ALERT 🚨\n{header}"

        if event.message.media:
            caption = f"{header}\n\n{text}".strip() if text else header
            sent = await relay_media(event, bot, owner_id, caption=caption)
        else:
            sent = await bot.send_message(owner_id, f"{header}\n\n{text}")

        message_map[str(sent.id)] = {"account_id": acc_id, "chat_id": event.chat_id}
        save_message_map(message_map)
        log.info(f"[{account['name']}] Message from {full_name} forwarded")

    # --- Reply Handler ---
    @bot.on(events.NewMessage(incoming=True, chats=owner_id))
    async def on_owner_reply(event):
        if not event.is_reply:
            await event.reply("❌ To reply, use Reply on the forwarded message.")
            return
        
        replied = await event.get_reply_message()
        info = message_map.get(str(replied.id))
        if not info:
            await event.reply("❌ Message info not found (hub may have restarted).")
            return

        acc_id = info["account_id"]
        chat_id = info["chat_id"]
        if acc_id not in user_clients:
            await event.reply("❌ Account not connected.")
            return

        client = user_clients[acc_id]
        if event.message.media:
            await relay_media(event, client, chat_id, caption=event.raw_text or None)
        else:
            if not event.raw_text or not event.raw_text.strip():
                await event.reply("❌ Please type a message.")
                return
            await client.send_message(chat_id, event.raw_text)

        await event.reply("✅ Sent")
        log.info(f"Reply sent successfully")

    # --- Callback Handlers ---
    @bot.on(events.CallbackQuery())
    async def on_callback(event):
        query = event.data.decode()
        
        try:
            if query == "main_menu":
                await show_main_menu(bot, owner_id, config, event.message.id)
            elif query == "manage_accounts":
                await show_manage_accounts(bot, owner_id, config, event.message.id)
            elif query == "add_account":
                await event.answer()
                await bot.send_message(owner_id, "📝 Enter account name:")
                current_add_account_flow['waiting_for_name'] = True
            elif query.startswith("account_"):
                aid = query.replace("account_", "")
                await show_account_options(bot, owner_id, config, aid, event.message.id)
            elif query.startswith("edit_name_"):
                aid = query.replace("edit_name_", "")
                await event.answer()
                await bot.send_message(owner_id, "✏️ Enter new account name:")
                current_add_account_flow['waiting_for_edit'] = aid
            elif query.startswith("toggle_"):
                aid = query.replace("toggle_", "")
                acc = toggle_account_active(config, aid)
                if acc:
                    status = "Active ✅" if acc["active"] else "Inactive ⭕"
                    await event.answer(f"✅ Account set to {status}")
                    await show_account_options(bot, owner_id, config, aid, event.message.id)
            elif query.startswith("remove_"):
                aid = query.replace("remove_", "")
                acc = next((a for a in config["accounts"] if a["id"] == aid), None)
                if acc:
                    buttons = [
                        [Button.inline("✅ Yes, Remove", f"confirm_remove_{aid}".encode())],
                        [Button.inline("❌ No, Cancel", f"account_{aid}".encode())]
                    ]
                    text = f"⚠️ Are you sure?\nRemove \"{acc['name']}\" account?\nThis cannot be undone."
                    await bot.edit_message(owner_id, event.message.id, text, buttons=buttons)
            elif query.startswith("confirm_remove_"):
                aid = query.replace("confirm_remove_", "")
                remove_account_from_config(config, aid)
                if aid in user_clients:
                    try: await user_clients[aid].disconnect()
                    except: pass
                    del user_clients[aid]
                await event.answer("✅ Account removed")
                await show_manage_accounts(bot, owner_id, config, event.message.id)
            elif query == "settings":
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "settings_keywords":
                buttons = [
                    [Button.inline("✏️ Edit Keywords", b"edit_keywords")],
                    [Button.inline("✅ Enable", b"enable_keywords"), Button.inline("❌ Disable", b"disable_keywords")],
                    [Button.inline("🔙 Back", b"settings")]
                ]
                kw_text = ", ".join(config["settings"]["keywords"]) if config["settings"]["keywords"] else "None"
                status = "Enabled ✅" if config["settings"]["keywords_enabled"] else "Disabled ⭕"
                text = f"🔔 KEYWORD ALERTS\n\nStatus: {status}\nKeywords: {kw_text}"
                await bot.edit_message(owner_id, event.message.id, text, buttons=buttons)
            elif query == "edit_keywords":
                await event.answer()
                await bot.send_message(owner_id, "Enter keywords (comma-separated):")
                current_add_account_flow['waiting_for_keywords'] = True
            elif query == "enable_keywords":
                config["settings"]["keywords_enabled"] = True
                save_config(config)
                await event.answer("✅ Keyword alerts enabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "disable_keywords":
                config["settings"]["keywords_enabled"] = False
                save_config(config)
                await event.answer("✅ Keyword alerts disabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "settings_voice":
                buttons = [
                    [Button.inline("✏️ Change Language", b"change_voice_lang")],
                    [Button.inline("✅ Enable", b"enable_voice"), Button.inline("❌ Disable", b"disable_voice")],
                    [Button.inline("🔙 Back", b"settings")]
                ]
                status = "Enabled ✅" if config["settings"]["transcribe_voice"] else "Disabled ⭕"
                text = f"🎙️ VOICE TRANSCRIPTION\n\nStatus: {status}\nLanguage: {config['settings']['voice_lang']}"
                await bot.edit_message(owner_id, event.message.id, text, buttons=buttons)
            elif query == "enable_voice":
                config["settings"]["transcribe_voice"] = True
                save_config(config)
                await event.answer("✅ Voice transcription enabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "disable_voice":
                config["settings"]["transcribe_voice"] = False
                save_config(config)
                await event.answer("✅ Voice transcription disabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "settings_translate":
                buttons = [
                    [Button.inline("✏️ Set Language", b"set_translate_lang")],
                    [Button.inline("✅ Enable", b"enable_translate"), Button.inline("❌ Disable", b"disable_translate")],
                    [Button.inline("🔙 Back", b"settings")]
                ]
                status = "Enabled ✅" if config["settings"]["translate_enabled"] else "Disabled ⭕"
                lang = config["settings"]["translate_target"] or "None"
                text = f"🌐 AUTO-TRANSLATE\n\nStatus: {status}\nTarget Language: {lang}"
                await bot.edit_message(owner_id, event.message.id, text, buttons=buttons)
            elif query == "enable_translate":
                config["settings"]["translate_enabled"] = True
                save_config(config)
                await event.answer("✅ Auto-translate enabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "disable_translate":
                config["settings"]["translate_enabled"] = False
                save_config(config)
                await event.answer("✅ Auto-translate disabled")
                await show_settings(bot, owner_id, config, event.message.id)
            elif query == "status":
                await show_status(bot, owner_id, config, event.message.id)
            elif query == "stop_hub":
                await event.answer("Stopping hub...")
                await bot.send_message(owner_id, "✅ Hub stopped.")
                await bot.disconnect()
                for client in user_clients.values():
                    await client.disconnect()
                sys.exit(0)
        except Exception as e:
            log.error(f"Callback error: {e}")
            await event.answer("❌ Error occurred.", alert=True)

    # --- Text Input Handlers for Setup Flow ---
    @bot.on(events.NewMessage(incoming=True, chats=owner_id))
    async def on_text_input(event):
        text = event.raw_text
        if not text: return

        # Waiting for Account Name
        if current_add_account_flow.get('waiting_for_name'):
            current_add_account_flow['waiting_for_name'] = False
            name = text
            await bot.send_message(owner_id, f"✅ Name set: {name}\nEnter phone number (e.g., +880123456789):")
            current_add_account_flow['waiting_for_phone'] = True
        
        elif current_add_account_flow.get('waiting_for_phone'):
            current_add_account_flow['waiting_for_phone'] = False
            phone = text
            try:
                account = add_account_to_config(config, name, phone)
                client = TelegramClient(account["session"], config["api_id"], config["api_hash"])
                await client.start(phone=phone)
                user_clients[account["id"]] = client
                log.info(f"Account {account['name']} connected")
                await bot.send_message(owner_id, f"✅ Account '{account['name']}' added successfully!\n\n📋 Manage Accounts updated.")
                await show_manage_accounts(bot, owner_id, config)
            except Exception as e:
                await bot.send_message(owner_id, f"❌ Error adding account: {e}")
        
        # Waiting for Edit Name
        elif current_add_account_flow.get('waiting_for_edit'):
            aid = current_add_account_flow['waiting_for_edit']
            current_add_account_flow['waiting_for_edit'] = None
            new_name = text
            edit_account_name(config, aid, new_name)
            await bot.send_message(owner_id, f"✅ Name updated to '{new_name}'")
            await show_account_options(bot, owner_id, config, aid, event.message.id)
        
        # Waiting for Keywords
        elif current_add_account_flow.get('waiting_for_keywords'):
            current_add_account_flow['waiting_for_keywords'] = False
            keywords = [k.strip() for k in text.split(",") if k.strip()]
            config["settings"]["keywords"] = keywords
            save_config(config)
            await bot.send_message(owner_id, "✅ Keywords updated!")
            await show_settings(bot, owner_id, config, event.message.id)

    await bot.run_until_disconnected()
