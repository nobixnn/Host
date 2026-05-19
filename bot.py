import os
import telebot
import subprocess
import zipfile
import shutil

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = "7992708923:AAGemnJ94TFf7ft8LyoG8JNqKUDkSty4RDo"
ADMIN_ID = 8150875959

BASE_DIR = "/root/hosts/"

bot = telebot.TeleBot(TOKEN)

# ================= DATA =================
allowed_users = [ADMIN_ID]
user_step = {}
host_data = {}
DATA = {}
running_process = {}

# ================= ACCESS =================
def is_allowed(uid):
    return uid in allowed_users

# ================= ADMIN =================
@bot.message_handler(commands=['adduser'])
def add_user(msg):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(msg.text.split()[1])
        if uid not in allowed_users:
            allowed_users.append(uid)
            bot.reply_to(msg, f"✅ Added {uid}")
    except:
        bot.reply_to(msg, "Use: /adduser user_id")

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id):
        return bot.reply_to(msg, "❌ Access Denied")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🚀 Host", callback_data="host"),
        InlineKeyboardButton("🤖 Bots", callback_data="bots")
    )
    markup.add(
        InlineKeyboardButton("📁 Files", callback_data="files")
    )

    bot.send_message(
        msg.chat.id,
        "🔥 VPS HOSTING PANEL\n\nSelect option:",
        reply_markup=markup
    )

# ================= HOST FLOW =================
@bot.callback_query_handler(func=lambda c: c.data == "host")
def host_start(call):
    if not is_allowed(call.from_user.id):
        return

    user_step[call.from_user.id] = {"step": "name"}
    bot.edit_message_text("👉 Enter bot name:", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda msg: msg.from_user.id in user_step)
def steps(msg):
    uid = msg.from_user.id
    step = user_step[uid]["step"]

    if step == "name":
        user_step[uid]["name"] = msg.text
        user_step[uid]["step"] = "repo"
        bot.reply_to(msg, "🔗 Send GitHub repo link")

    elif step == "repo":
        user_step[uid]["repo"] = msg.text
        user_step[uid]["step"] = "cmd"
        bot.reply_to(msg,
            "⚙️ Send ALL commands in ONE message\nExample:\n"
            "pip install -r requirements.txt\npython bot.py"
        )

    elif step == "cmd":
        raw_cmds = msg.text.split("\n")
        commands = [c.strip() for c in raw_cmds if c.strip()]

        name = user_step[uid]["name"]
        repo = user_step[uid]["repo"]

        bot.reply_to(msg, "⏳ Hosting started...")

        run_host(msg, name, repo, commands)

        del user_step[uid]

# ================= PROGRESS HOST =================
def run_host(msg, name, repo, commands):
    path = BASE_DIR + name

    total_steps = len(commands) + 1
    current = 0

    progress = bot.send_message(msg.chat.id, "⏳ Starting...")

    def update():
        percent = int((current / total_steps) * 100)
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)

        bot.edit_message_text(
            f"⏳ Hosting: {name}\n\n[{bar}] {percent}%",
            msg.chat.id,
            progress.message_id
        )

    try:
        # Clone
        subprocess.run(f"git clone {repo} {path}", shell=True)
        current += 1
        update()

        # Commands
        for cmd in commands:
            subprocess.run(f"cd {path} && {cmd}", shell=True)
            current += 1
            update()

        # Save data
        DATA[name] = {
            "path": path,
            "commands": commands
        }

        bot.edit_message_text(
            f"✅ Host Complete: {name}",
            msg.chat.id,
            progress.message_id
        )

    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

# ================= BOTS =================
@bot.callback_query_handler(func=lambda c: c.data == "bots")
def bots(call):
    if not is_allowed(call.from_user.id):
        return

    markup = InlineKeyboardMarkup()

    for name in DATA:
        markup.add(InlineKeyboardButton(name, callback_data=f"bot_{name}"))

    bot.edit_message_text(
        "🤖 Your Bots:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ================= BOT PANEL =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("bot_"))
def bot_panel(call):
    name = call.data.split("_")[1]

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("▶️ Start", callback_data=f"start_{name}"),
        InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{name}")
    )
    markup.add(
        InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{name}"),
        InlineKeyboardButton("❌ Delete", callback_data=f"delete_{name}")
    )

    bot.edit_message_text(
        f"⚙️ {name} Control Panel",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ================= CONTROLS =================
@bot.callback_query_handler(func=lambda c: True)
def control(call):
    data = call.data

    if data.startswith("start_"):
        name = data.split("_")[1]
        cmds = DATA[name]["commands"]
        start_cmd = cmds[-1]

        process = subprocess.Popen(
            f"cd {DATA[name]['path']} && {start_cmd}",
            shell=True
        )

        running_process[name] = process
        bot.answer_callback_query(call.id, "Started")

    elif data.startswith("stop_"):
        name = data.split("_")[1]

        if name in running_process:
            running_process[name].terminate()

        bot.answer_callback_query(call.id, "Stopped")

    elif data.startswith("restart_"):
        name = data.split("_")[1]

        if name in running_process:
            running_process[name].terminate()

        cmds = DATA[name]["commands"]
        start_cmd = cmds[-1]

        process = subprocess.Popen(
            f"cd {DATA[name]['path']} && {start_cmd}",
            shell=True
        )

        running_process[name] = process
        bot.answer_callback_query(call.id, "Restarted")

    elif data.startswith("delete_"):
        name = data.split("_")[1]

        if name in running_process:
            running_process[name].terminate()

        shutil.rmtree(DATA[name]["path"], ignore_errors=True)
        del DATA[name]

        bot.answer_callback_query(call.id, "Deleted")

# ================= FILES =================
@bot.callback_query_handler(func=lambda c: c.data == "files")
def files(call):
    base = BASE_DIR

    for name in DATA:
        zip_path = f"/root/{name}.zip"

        shutil.make_archive(f"/root/{name}", 'zip', DATA[name]["path"])
        bot.send_document(call.message.chat.id, open(zip_path, 'rb'))

# ================= RUN =================
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

print("Bot running...")
bot.infinity_polling()
