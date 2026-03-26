import logging
import io
import re
from datetime import time, timezone
from threading import Thread
from flask import Flask

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ==========================
# CONFIG
# ==========================
BOT_TOKEN = "8715479969:AAG5HPiFBSgzySaugO8WQE5jx3Majq928Ds  # @BotFather token
GROUP_ID  = -1001234567890         # Telegram group ID

# ==========================
# LOGGING
# ==========================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ==========================
# GLOBAL STATE
# ==========================
session_active       = False
post_counter         = 0
session_posts: list  = []
current_session_num  = 0
prev_defaulters: list = []
all_participants: set = set()
done_users: set      = set()

# ==========================
# HELPERS
# ==========================
def extract_twitter_link(text: str):
    m = re.search(r"https?://(www\.)?(twitter\.com|x\.com)/\S+", text)
    return m.group(0) if m else None

def build_txt(session_num: int) -> bytes:
    lines = [f"SESSION {session_num} — ALL LINKS\n{'='*40}\n\n"]
    for p in session_posts:
        lines.append(
            f"Post {p['num']}\n"
            f"Name    : {p['name']}\n"
            f"Username: {p['username']}\n"
            f"Link    : {p['link']}\n\n"
        )
    lines.append(f"{'='*40}\nTotal: {len(session_posts)} posts\n")
    return "".join(lines).encode("utf-8")

# ==========================
# SESSION HANDLERS
# ==========================
async def open_session(context: ContextTypes.DEFAULT_TYPE):
    global session_active, post_counter, session_posts
    global current_session_num, all_participants, done_users

    session_active      = True
    post_counter        = 0
    session_posts       = []
    all_participants    = set()
    done_users          = set()
    current_session_num += 1

    def_text = ""
    if prev_defaulters:
        mentions = " ".join(prev_defaulters)
        def_text = f"\n\n⚠️ *আগের session এর defaulters:*\n{mentions}\n_আগের session complete করো আগে!_"

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=(
            f"🟢 SESSION {current_session_num} OPEN!\n"
            f"Drop your link, group open! ⏰ ১ মিনিট সময় আছে"
            f"{def_text}"
        ),
        parse_mode="Markdown"
    )

async def close_session(context: ContextTypes.DEFAULT_TYPE):
    global session_active, prev_defaulters

    if not session_active:
        return
    session_active = False

    new_def = list(all_participants - done_users)
    prev_defaulters = new_def

    def_text = "\n\n❌ *Defaulters:*\n" + " ".join(new_def) if new_def else "\n\n✅ সবাই engage করেছে! 🎉"

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=(
            f"🔴 SESSION {current_session_num} CLOSED\n\n"
            f"📊 Total posts: *{len(session_posts)}*\n"
            f"✅ Done: *{len(done_users)}*"
            f"{def_text}\n\n"
            f"_নিচের file এ সব link আছে — এখন engage শুরু করো_"
        ),
        parse_mode="Markdown"
    )

    if session_posts:
        await context.bot.send_document(
            chat_id=GROUP_ID,
            document=io.BytesIO(build_txt(current_session_num)),
            filename=f"session_{current_session_num}.txt",
            caption=f"📋 Session {current_session_num} — {len(session_posts)} টা link"
        )

# ==========================
# REMINDER
# ==========================
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text="⏰ ১ মিনিট পরে session শুরু হবে! Ready হও 🚀 আগের engage বাকি থাকলে এখনই করো!",
        parse_mode="Markdown"
    )

# ==========================
# MESSAGE HANDLER
# ==========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global post_counter

    msg = update.message
    if not msg or not msg.text:
        return
    if not session_active or msg.chat_id != GROUP_ID:
        return

    link = extract_twitter_link(msg.text.strip())
    if not link:
        return

    user      = msg.from_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    username  = f"@{user.username}" if user.username else f"@id{user.id}"

    post_counter += 1
    session_posts.append({"num": post_counter, "name": full_name, "username": username, "link": link})
    all_participants.add(username)

    try: await msg.delete()
    except: pass

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"Post {post_counter}\n\nName: {full_name}\nUsername: {username}\n\n• {link}"
    )

# ==========================
# /done COMMAND
# ==========================
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.chat_id != GROUP_ID:
        return

    user     = msg.from_user
    username = f"@{user.username}" if user.username else f"@id{user.id}"

    if username not in all_participants:
        await msg.reply_text("❌ তুমি এই session এ link দাওনি!")
        return

    done_users.add(username)
    try: await msg.delete()
    except: pass
    await context.bot.send_message(chat_id=GROUP_ID, text=f"✅ {username} — engage confirmed! 👍")

# ==========================
# /status COMMAND
# ==========================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat_id != GROUP_ID:
        return

    pending = all_participants - done_users
    p_text  = "\n".join(pending) if pending else "কেউ নেই ✅"

    await update.message.reply_text(
        f"📊 *Session {current_session_num}*\n\n"
        f"🟢 Active: {'হ্যাঁ' if session_active else 'না'}\n"
        f"📝 Posts: {len(session_posts)}\n"
        f"✅ Done: {len(done_users)}\n"
        f"⏳ Pending ({len(pending)}):\n{p_text}",
        parse_mode="Markdown"
    )

# ==========================
# MANUAL OPEN/CLOSE
# ==========================
async def manual_open(update: Update, context: ContextTypes.DEFAULT_TYPE): await open_session(context)
async def manual_close(update: Update, context: ContextTypes.DEFAULT_TYPE): await close_session(context)

# ==========================
# FLASK KEEP-ALIVE
# ==========================
flask_app = Flask('')

@flask_app.route('/')
def home(): return "Bot is alive!"

def run(): flask_app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run).start()

# ==========================
# TRIAL SCHEDULER
# ==========================
def setup_trial_jobs(jq):
    start_hour = 4  # UTC
    start_min  = 35 # 10:35 BD
    for i in range(5):
        # Open
        jq.run_daily(open_session,  time(start_hour, (start_min + i*2) % 60, tzinfo=timezone.utc))
        # Close 1 min later
        jq.run_daily(close_session, time(start_hour, (start_min + i*2 + 1) % 60, tzinfo=timezone.utc))

# ==========================
# MAIN
# ==========================
def main():
    keep_alive()
    app_ = ApplicationBuilder().token(BOT_TOKEN).build()

    app_.add_handler(CommandHandler("done",         done_command))
    app_.add_handler(CommandHandler("status",       status_command))
    app_.add_handler(CommandHandler("opensession",  manual_open))
    app_.add_handler(CommandHandler("closesession", manual_close))
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup trial
    setup_trial_jobs(app_.job_queue)

    print("✅ Trial Bot চালু! Ctrl+C দিয়ে বন্ধ করা যাবে")
    app_.run_polling()

if __name__ == "__main__":
    main()
