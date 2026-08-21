import asyncio
import html
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import content
import kai
import xfeed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# All user-facing text lives in content/*.yml (updated via pull request).
TEXTS, CONTENT_COMMANDS, MENUS, PROJECTS = content.load()

bot = AsyncTeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
new_users = set()
new_users_lock = asyncio.Lock()

# Configuration
CAPTCHA_TIMEOUT = 180  # 3 minutes
BAN_DURATION_DAYS = 7
REQUEST_TIMEOUT = 10

# Main group for X auto-posts; unset disables the auto-poster.
MAIN_CHAT_ID = os.environ.get('MAIN_CHAT_ID', '').strip()
X_POLL_SECONDS = max(60, int(os.environ.get('X_POLL_SECONDS', '300')))


def mention(user):
    """Readable, HTML-safe reference to a user (usernames are optional)."""
    if user.username:
        return f'@{user.username}'
    if user.first_name:
        return html.escape(user.first_name, quote=False)
    return f'User{user.id}'


def create_main_menu_keyboard():
    """Create a modern inline keyboard for main navigation"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Row 1: Essential commands
    keyboard.add(
        InlineKeyboardButton("📚 Guides", callback_data="guides"),
        InlineKeyboardButton("🔗 Projects", callback_data="projects")
    )

    # Row 2: Trading & Info
    keyboard.add(
        InlineKeyboardButton("💱 Exchanges", callback_data="exchanges"),
        InlineKeyboardButton("💳 Wallets", callback_data="wallets")
    )

    # Row 3: Community & Support
    keyboard.add(
        InlineKeyboardButton("🌍 International", callback_data="international"),
        InlineKeyboardButton("📱 Social Media", callback_data="social")
    )

    # Row 4: Advanced
    keyboard.add(
        InlineKeyboardButton("🔥 Stake/Burn", callback_data="stake"),
        InlineKeyboardButton("📄 Whitepaper", callback_data="whitepaper")
    )

    return keyboard


async def send_message(chat_id, message, link_preview=False, html=True, reply_markup=None, reply_to=None):
    """Universal message sender that uses the provided chat_id."""
    reply_parameters = None
    if reply_to is not None:
        # Replying also places the message in the right forum topic.
        reply_parameters = telebot.types.ReplyParameters(
            message_id=reply_to, allow_sending_without_reply=True)
    try:
        return await bot.send_message(
            chat_id,
            message,
            parse_mode='HTML' if html else None,
            link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=not link_preview),
            reply_markup=reply_markup,
            reply_parameters=reply_parameters
        )
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return None


async def schedule_message_deletion(chat_id, message_id, delay_seconds=60):
    """Schedules a message to be deleted after a specified delay."""
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.warning(f"Could not delete message {message_id} from chat {chat_id}: {e}")

# --- Main Handlers ---

@bot.message_handler(content_types=['new_chat_members'])
async def handle_welcome(message):
    """Handles new members, presenting them with a captcha."""
    current_chat_id = message.chat.id
    try:
        await bot.delete_message(current_chat_id, message.id)
    except:
        pass  # Bot may not have admin rights to delete, proceed anyway

    from_user = await bot.get_chat_member(current_chat_id, message.from_user.id)

    # If the new member is an admin or the owner, welcome them directly
    if from_user.status in ['creator', 'administrator']:
        await welcome_new_users(message, message.new_chat_members)
        return

    # For all other new members, present the captcha challenge
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, selective=True, resize_keyboard=True)
    options = ['🔮 Koinos', '₿ Bitcoin', '🔷 Ethereum']
    random.shuffle(options)
    markup.add(*options)

    captcha_messages = []
    async with new_users_lock:
        for member in message.new_chat_members:
            new_users.add(member.id)
            welcome_text = f"""🎉 <b>Welcome {mention(member)}!</b>

🛡️ <i>Quick security check:</i>
What is the name of this blockchain project?

⏰ <i>You have 3 minutes to respond...</i>"""

            captcha_msg = await send_message(current_chat_id, welcome_text, reply_markup=markup)
            if captcha_msg:
                captcha_messages.append(captcha_msg)

    # Wait for the timeout and then clean up
    await asyncio.sleep(CAPTCHA_TIMEOUT)
    for captcha_message in captcha_messages:
        try:
            await bot.delete_message(captcha_message.chat.id, captcha_message.message_id)
        except:
            pass

    async with new_users_lock:
        for member in message.new_chat_members:
            if member.id in new_users:
                new_users.remove(member.id)
                await kick_user(current_chat_id, member)


@bot.message_handler(commands=['info', 'start', 'menu'])
async def send_info(message):
    """Displays the main info menu and deletes the user's command."""
    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.warning(f"Could not delete command message: {e}")

    sent_message = await send_message(message.chat.id, TEXTS['main_menu'],
                                      reply_markup=create_main_menu_keyboard())
    if sent_message:
        asyncio.create_task(schedule_message_deletion(sent_message.chat.id, sent_message.message_id))


@bot.message_handler(commands=['report'])
async def send_report(message):
    """Alerts administrators."""
    report_text = """🚨 <b>ADMIN ALERT</b> 🚨

<b>Someone needs attention from moderators:</b>
@kuixihe @weleleliano @saleh_hawi @fifty2kph

⚠️ <i>Reported by:</i> {username}
🕐 <i>Time:</i> {time}""".format(
        username=mention(message.from_user),
        time=datetime.now().strftime("%H:%M:%S")
    )

    await send_message(message.chat.id, report_text)


# --- Projects & Updates (rendered from content/projects.yml) ---

@bot.message_handler(commands=['projects'])
async def handle_projects(message):
    """Lists all ecosystem projects, grouped by category."""
    await send_message(message.chat.id, content.render_projects_overview(PROJECTS))


@bot.message_handler(commands=['project'])
async def handle_project(message):
    """Shows details and latest updates for a single project."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        ids = ', '.join(p['id'] for p in PROJECTS)
        if len(ids) > 3500:
            ids = ids[:3500] + '…'
        await send_message(
            message.chat.id,
            f'🔎 <b>Usage:</b> /project &lt;name&gt;\n\n<b>Available:</b> {ids}'
        )
        return
    project = content.find_project(PROJECTS, parts[1])
    if project is None:
        safe_query = html.escape(parts[1], quote=False)
        await send_message(
            message.chat.id,
            f'❓ No project found for "{safe_query}". Try /projects for the full list.'
        )
        return
    await send_message(message.chat.id, content.render_project_detail(project))


@bot.message_handler(commands=['updates'])
async def handle_updates(message):
    """Shows the latest updates across all projects."""
    await send_message(message.chat.id, content.render_updates(PROJECTS))


@bot.message_handler(commands=['x'])
async def handle_x(message):
    """Shows the latest X post from @KoinosNetwork."""
    post = await xfeed.get_latest_cached()
    if post is None:
        await send_message(message.chat.id, xfeed.fallback_message(), link_preview=True)
        return
    await send_message(
        message.chat.id,
        xfeed.format_post(post, f'🐦 <b>Latest post from {xfeed.PROFILE_NAME}</b>'),
        link_preview=True,
    )


# --- Static commands (defined in content/commands.yml) ---

def _register_content_commands():
    for name, cfg in CONTENT_COMMANDS.items():
        commands = [name, *cfg.get('aliases', [])]

        async def handler(message, _text=cfg['text'],
                          _preview=cfg.get('link_preview', False)):
            await send_message(message.chat.id, _text, link_preview=_preview)

        bot.message_handler(commands=commands)(handler)


_register_content_commands()


# --- Menu Redirects ---
# Commands that are part of the main menu buttons redirect to the main menu.
@bot.message_handler(commands=[
    'guides', 'docs', 'international', 'exchange', 'exchanges', 'cex',
    'buy', 'media', 'social', 'stake', 'whitepaper', 'wallets'
])
async def handle_menu_redirects(message):
    """Handles commands that are now buttons in the main menu by showing the menu."""
    await send_info(message)


# --- Kai (@kai) — AI assistant via the Koinos AI worker network ---

async def _typing_loop(chat_id, thread_id):
    """Re-sends the typing indicator while Kai waits on the network;
    without it the bot looks dead during a cold model load."""
    while True:
        try:
            await bot.send_chat_action(chat_id, 'typing', message_thread_id=thread_id)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug(f'typing indicator failed: {e}')
        await asyncio.sleep(4)


@bot.message_handler(func=lambda m: kai.is_trigger(m.text), content_types=['text'])
async def handle_kai(message):
    """Answers @kai mentions in the main group via the Koinos AI network."""
    async with new_users_lock:
        unverified = message.from_user.id in new_users
    if unverified:
        # Captcha first — hand the message to the security handler.
        await handle_text_messages(message)
        return
    if not kai.enabled():
        return
    chat_id = message.chat.id
    if not MAIN_CHAT_ID or str(chat_id) != MAIN_CHAT_ID:
        # Kai is exclusive to the official group; in DMs say where to
        # find it, everywhere else stay silent.
        if message.chat.type == 'private':
            await send_message(chat_id, kai.GROUP_ONLY_TEXT)
        return

    question = kai.extract_question(message.text)
    if not question:
        await send_message(chat_id, kai.HELP_TEXT, reply_to=message.message_id)
        return
    cooldown = kai.user_cooldown_remaining(message.from_user.id)
    if cooldown:
        notice = await send_message(
            chat_id,
            f'🕐 {mention(message.from_user)}, one question per '
            f'{kai.cooldown_seconds()}s — try again in {cooldown}s.',
            reply_to=message.message_id)
        if notice:
            asyncio.create_task(schedule_message_deletion(
                notice.chat.id, notice.message_id, delay_seconds=8))
        return
    if not kai.window_allows():
        await send_message(chat_id, kai.QUOTA_TEXT, reply_to=message.message_id)
        return

    thread_id = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
    typing_task = asyncio.create_task(_typing_loop(chat_id, thread_id))
    try:
        result = await kai.ask(question)
    finally:
        typing_task.cancel()
    await send_message(chat_id, result['text'], reply_to=message.message_id)


# --- Security Handler (Must be last text-based handler) ---

@bot.message_handler(content_types=['text'])
async def handle_text_messages(message):
    """Handles all text from unverified users, enforcing the captcha."""
    async with new_users_lock:
        if message.from_user.id in new_users:
            try:
                await bot.delete_message(message.chat.id, message.id)
            except:
                pass

            # If the message is a reply to the captcha, handle it
            if message.reply_to_message is not None:
                await handle_captcha_response(message)
            else:
                logger.warning(f"User {message.from_user.username} ({message.from_user.id}) tried to send message before completing captcha")
                warning_msg = await send_message(
                    message.chat.id,
                    f"⚠️ <b>{mention(message.from_user)}</b>, please complete the security check first!"
                )
                await asyncio.sleep(3)
                try:
                    await bot.delete_message(warning_msg.chat.id, warning_msg.message_id)
                except:
                    pass
            return

# --- Helper Functions ---

async def handle_captcha_response(message):
    """Handles the user's response to the captcha question."""
    if message.from_user.id not in new_users:
        return
    new_users.remove(message.from_user.id)

    try:
        await bot.delete_message(message.chat.id, message.reply_to_message.id)
        await bot.delete_message(message.chat.id, message.id)
    except:
        pass

    correct_answers = ['🔮 Koinos', 'Koinos', 'koinos', 'KOINOS']
    if message.text not in correct_answers:
        goodbye_msg = await send_message(
            message.chat.id,
            f"❌ <b>Incorrect answer, {mention(message.from_user)}</b>\n\n"
            f"🚪 <i>Please try again when you're ready to join our community!</i>"
        )
        await asyncio.sleep(2)
        try:
            await bot.delete_message(goodbye_msg.chat.id, goodbye_msg.message_id)
        except:
            pass
        await kick_user(message.chat.id, message.from_user)
        return

    await welcome_new_users(message, [message.from_user])


async def kick_user(chat_id, user):
    """Kicks a user from the chat."""
    try:
        await bot.kick_chat_member(chat_id, user.id, until_date=datetime.today() + timedelta(days=BAN_DURATION_DAYS))
        logger.info(f"Kicked user {user.username} ({user.id}) for failing captcha")
    except Exception as e:
        logger.error(f"Failed to kick user {user.username}: {e}")


async def welcome_new_users(message, users):
    """Sends a welcome message to verified new users."""
    usernames = [mention(user) for user in users]
    if len(usernames) > 1:
        usernames[-1] = 'and ' + usernames[-1]
    username_list = ', '.join(usernames) if len(usernames) > 2 else ' '.join(usernames)

    help_text = TEXTS['welcome'].replace('{usernames}', username_list)

    sent_message = await send_message(
        message.chat.id,
        help_text,
        reply_markup=create_main_menu_keyboard()
    )
    if sent_message:
        asyncio.create_task(schedule_message_deletion(sent_message.chat.id, sent_message.message_id))


@bot.message_handler(content_types=['left_chat_member'])
async def delete_leave_message(message):
    """Cleans up "user has left" messages."""
    try:
        await bot.delete_message(message.chat.id, message.id)
    except:
        pass

# --- Callback Query Handler ---

@bot.callback_query_handler(func=lambda call: True)
async def handle_callback_query(call):
    """Handles all inline keyboard button presses."""
    try:
        if call.data == "main_menu":
            text = TEXTS['main_menu']
        elif call.data == "projects":
            text = content.render_projects_overview(PROJECTS)
        else:
            text = MENUS.get(call.data, "")

        if text:
            await bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                        parse_mode='HTML', reply_markup=create_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Callback error: {e}")

    await bot.answer_callback_query(call.id)

# --- Main Execution ---

async def main():
    logger.info("🚀 Koinos Bot starting up...")
    if MAIN_CHAT_ID:
        asyncio.create_task(
            xfeed.autopost_loop(send_message, int(MAIN_CHAT_ID), X_POLL_SECONDS))
    else:
        logger.info("MAIN_CHAT_ID not set — X auto-posting disabled")
    if kai.enabled() and MAIN_CHAT_ID:
        logger.info("Kai (@kai) enabled for the main group")
    else:
        logger.info("Kai (@kai) disabled (KAI_API_URL or MAIN_CHAT_ID not set)")
    try:
        await bot.polling(non_stop=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Koinos Bot shutting down...")
        await bot.stop_polling()
        await bot.close_session()

if __name__ == '__main__':
    asyncio.run(main())
