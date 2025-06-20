import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

bot = AsyncTeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
new_users = set()
new_users_lock = asyncio.Lock()

# Configuration
CAPTCHA_TIMEOUT = 180  # 3 minutes
BAN_DURATION_DAYS = 7
REQUEST_TIMEOUT = 10

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

async def send_message(chat_id, message, link_preview=False, html=True, reply_markup=None):
    """Universal message sender that uses the provided chat_id."""
    try:
        return await bot.send_message(
            chat_id,
            message,
            parse_mode='HTML' if html else None,
            link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=not link_preview),
            reply_markup=reply_markup
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
            welcome_text = f"""🎉 <b>Welcome @{member.username}!</b>

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
        
    help_text = """🔮 <b>Welcome to Koinos Bot!</b>

🔥 <b>Quick Commands:</b>
/claim - Token claiming info
/price - Price discussion rules  
/supply - Token supply info
/mana - Learn about Mana
/roadmap - Development roadmap
/rules - Community guidelines

💫 <i>Choose an option below to get started!</i>"""
    
    sent_message = await send_message(message.chat.id, help_text, reply_markup=create_main_menu_keyboard())
    if sent_message:
        asyncio.create_task(schedule_message_deletion(sent_message.chat.id, sent_message.message_id))

@bot.message_handler(commands=['mana'])
async def handle_mana(message):
    """Provides an explanation of Mana."""
    await send_message(message.chat.id, """🔮 <b>The Magic of Mana</b>

✨ <b>What is Mana?</b>
Mana is the secret sauce that makes Koinos special! Every KOIN token contains inherent Mana that powers blockchain transactions.

🎮 <b>Just Like Video Games:</b>
• Use Mana for transactions
• Mana regenerates automatically over time  
• Never run out permanently
• Use Koinos forever without fees!

⚡ <b>Key Benefits:</b>
• No transaction fees
• Sustainable usage model
• Beginner-friendly experience

🔗 <b>Deep Dive:</b>
<a href="https://docs.koinos.io/overview/mana/">Complete Mana Guide</a>

💫 <i>Welcome to fee-less blockchain interactions!</i>""")

@bot.message_handler(commands=['rules','guidelines'])
async def handle_rules(message):
    """Displays the community guidelines."""
    await send_message(message.chat.id, """🛡️ <b>Koinos Community Guidelines</b>

<i>Building the future together requires great collaboration!</i>

✅ <b>Encouraged Activities:</b>
• 🚀 Share your projects and innovations
• 💡 Discuss features, plans, and ideas
• 🔄 Provide constructive feedback
• 🤝 Maintain respectful conversations
• 🌱 Help grow our ecosystem
• 📚 Share insights and resources

❌ <b>Please Avoid:</b>
• 🚫 Promoting non-utility tokens
• 📈 Price speculation (use @thekoinosarmy)
• 🗣️ Off-topic discussions
• 🎭 Disrespectful behavior

🎯 <b>Our Mission:</b>
Create a positive, innovative environment where everyone can learn, build, and grow together.

📄 <b>Complete Guidelines:</b>
🔗 <a href="https://docs.google.com/document/d/1-WYFlj7p3U0GG5Q5_OQPR5tzRD4WlG3FKNj4u9Lz3vQ/edit?usp=sharing">Read Full Guidelines</a>

💫 <i>Welcome to our amazing community!</i>""")

@bot.message_handler(commands=['claim'])
async def handle_claim(message):
    """Displays information on how to claim tokens."""
    await send_message(message.chat.id, """🎁 <b>Token Claim Information</b>

⚠️ <b>Eligibility Check:</b>
✅ Must have held ERC-20 KOIN during snapshot
🔍 <a href="https://t.me/koinos_community/109226">Verify Your Address</a>

💳 <b>You'll Need a Koinos Wallet:</b>
🦊 <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Download Kondor Wallet</a>

🔐 <b>CRITICAL SECURITY WARNING:</b>
🚨 <b>BACKUP YOUR PRIVATE KEYS/SEED PHRASE!</b>
🚨 <b>We CANNOT recover lost keys!</b>

📚 <b>Step-by-Step Guides:</b>
📺 <a href="https://youtu.be/l-5dHGqUSj4">Video Tutorial</a>
📖 <a href="https://medium.com/@kuixihe/a-complete-guide-to-claiming-koin-tokens-edd20e7d9c40">Written Guide</a>

⏰ <b>No Rush:</b>
<i>There's no time limit - claim whenever you're ready!</i>

🔒 <i>Security first, claiming second!</i>""")

@bot.message_handler(commands=['report'])
async def send_report(message):
    """Alerts administrators."""
    report_text = """🚨 <b>ADMIN ALERT</b> 🚨

<b>Someone needs attention from moderators:</b>
@kuixihe @weleleliano @saleh_hawi @fifty2kph

⚠️ <i>Reported by:</i> @{username}
🕐 <i>Time:</i> {time}""".format(
        username=message.from_user.username or f"User{message.from_user.id}",
        time=datetime.now().strftime("%H:%M:%S")
    )
    
    await send_message(message.chat.id, report_text)

@bot.message_handler(commands=['website', 'websites'])
async def send_website(message):
    """Displays a link to the main website."""
    await send_message(
        message.chat.id,
        '🌐 <b><a href="https://koinos.io">Visit Koinos.io</a></b>\n\n'
        '✨ <i>Discover the future of blockchain technology!</i>', 
        True
    )

@bot.message_handler(commands=['supply'])
async def handle_supply(message):
    """Displays token supply information."""
    data = "🔄 <i>Data source updating...</i>"
    await send_message(message.chat.id, f"""📊 <b>KOIN Virtual Supply</b>

💰 <b>Current Supply:</b> {data}
<i>(KOIN + VHP combined)</i>

📈 <b>Learn More:</b>
🔗 <a href="https://docs.koinos.io/overview/tokenomics/">Koinos Tokenomics</a>

💡 <i>Virtual supply includes both circulating KOIN and burned VHP tokens</i>""")

@bot.message_handler(commands=['vhpsupply'])
async def handle_vhp_supply(message):
    """Displays VHP supply information."""
    data = "🔄 <i>Data source updating...</i>"
    await send_message(message.chat.id, f"""⚡ <b>VHP Total Supply</b>

🔥 <b>Current VHP Supply:</b> {data}

📈 <b>Learn More:</b>
🔗 <a href="https://docs.koinos.io/overview/tokenomics/">Koinos Tokenomics</a>

💡 <i>VHP (Virtual Hash Power) is created by burning KOIN tokens</i>""")

@bot.message_handler(commands=['roadmap'])
async def handle_roadmap(message):
    """Displays a link to the development roadmap."""
    await send_message(message.chat.id, """🗺️ <b>Koinos Development Roadmap</b>

🚀 <b>Track our progress:</b>
📍 <a href="https://koinos.io/#roadmap">Official Koinos Roadmap</a>

🎯 <b>What's Coming:</b>
• Enhanced developer tools
• Ecosystem expansion  
• Performance optimizations
• New partnership integrations

⚡ <i>The future of blockchain is being built daily!</i>""")

@bot.message_handler(commands=['price'])
async def handle_price(message):
    """Displays price discussion guidelines."""
    await send_message(message.chat.id, """📈 <b>Price Discussion Guidelines</b>

🚨 <b>Keep price talk out of this group!</b>

💬 <b>Price Discussions:</b>
🚀 <a href="https://t.me/thekoinosarmy">Koinos Army Telegram</a>

📊 <b>Live Price Data:</b>
📈 <a href="https://www.coingecko.com/en/coins/koinos">CoinGecko KOIN Price</a>

💡 <i>This channel focuses on technology, development, and community!</i>""")

@bot.message_handler(commands=['programs'])
async def handle_programs(message):
    """Displays a message indicating no active programs."""
    await send_message(
        message.chat.id,
        "✅ <b>No active programs right now.</b>\n\n<i>Check back soon for new initiatives!</i>"
    )

# --- Menu Redirects ---
# All commands that are part of the main menu buttons now redirect to the main menu.
@bot.message_handler(commands=[
    'guides', 'docs', 'international', 'exchange', 'exchanges', 'cex', 
    'buy', 'media', 'social', 'projects', 'stake', 'whitepaper', 'wallets'
])
async def handle_menu_redirects(message):
    """Handles commands that are now buttons in the main menu by showing the menu."""
    await send_info(message)


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
                    f"⚠️ <b>@{message.from_user.username}</b>, please complete the security check first!"
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
    async with new_users_lock:
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
            f"❌ <b>Incorrect answer, @{message.from_user.username}</b>\n\n"
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
    usernames = [f'@{user.username}' if user.username else f'User{user.id}' for user in users]
    if len(usernames) > 1:
        usernames[-1] = 'and ' + usernames[-1]
    username_list = ', '.join(usernames) if len(usernames) > 2 else ' '.join(usernames)

    help_text = f"""🎉 <b>Welcome {username_list}!</b>

🔥 <b>Quick Commands:</b>
/claim - Token claiming info
/price - Price discussion rules  
/supply - Token supply info
/mana - Learn about Mana
/roadmap - Development roadmap
/rules - Community guidelines

💫 <i>Choose an option below to get started!</i>"""

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
    text = ""
    try:
        if call.data == "main_menu":
            text = """🔮 <b>Welcome to Koinos Bot!</b>

🔥 <b>Quick Commands:</b>
/claim - Token claiming info
/price - Price discussion rules  
/supply - Token supply info
/mana - Learn about Mana
/roadmap - Development roadmap
/rules - Community guidelines

💫 <i>Choose an option below to get started!</i>"""
            
        elif call.data == "guides":
            text = """📚 <b>Koinos Learning Hub</b>

🎓 <b>Official Documentation:</b>
📖 <a href="https://docs.koinos.io">Complete Koinos Docs</a>

⚡ <b>Core Concepts:</b>
🔮 <a href="https://docs.koinos.io/overview/mana/">Master Mana Mechanics</a>

💡 <i>Start your Koinos journey with these essential guides!</i>"""
            
        elif call.data == "projects":
            text = """🚀 <b>Koinos Ecosystem Projects</b>

📱 <b>dApps & Platforms:</b>
🎨 <a href="https://kollection.app">Kollection</a> - NFT Marketplace
🏙️ <a href="https://koincity.com">Koincity</a> - Virtual World
📝 <a href="https://koinosbox.com/nicknames">Nicknames</a> - Name Service
🖼️ <a href="https://kanvas-app.com">Kanvas</a> - Creative Platform
🌱 <a href="https://koinosgarden.com">Koinos Garden</a> - DeFi

🎮 <b>Gaming:</b>
🚀 <a href="https://planetkoinos.com/space_striker.html">Space Striker</a> - Action Game

⛏️ <b>Mining & Staking:</b>
🔥 <a href="https://fogata.io">Fogata</a> - Mining Pool
💎 <a href="https://burnkoin.com">Burn Koin</a> - Staking Pool

🔍 <b>Infrastructure:</b>
📊 <a href="https://koinosblocks.com">KoinosBlocks</a> - Block Explorer

💳 <b>Wallets:</b>
🦊 <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Kondor</a> - Browser Extension (Suggested)
🌐 <a href="https://portal.armana.io">Portal</a> - Web Wallet
👑 <a href="https://sovrano.io/">Sovrano</a> - Wallet Solution (Suggested)

🤖 <b>AI & Tools:</b>
🧠 <a href="https://planetkoinos.com/koinos_ai.html">Koinos AI</a> - AI Assistant

🌟 <i>The ecosystem is growing daily!</i>"""
            
        elif call.data == "exchanges":
            text = """💱 <b>Trade $KOIN Everywhere</b>

📈 <b>Centralized Exchanges:</b>
🏪 <a href="https://www.mexc.com/exchange/KOIN_USDT">MEXC</a> - Global Exchange
⚡ <a href="https://bingx.com/en/spot/KOINUSDT/">BingX</a> - Crypto Trading

🔥 <b>More listings coming soon!</b>
<i>We're always working on new exchange partnerships</i>

⚠️ <i>Free to request exchanges, but no guarantees on timing!</i>"""
            
        elif call.data == "wallets":
            text = """💳 <b>Secure Your $KOIN</b>

<i>Choose the perfect wallet for your needs:</i>

🦊 <b>Kondor Wallet</b> - <i>Suggested • Active Development</i>
💻 Browser extension for Chrome & Brave
👨‍💻 Created by Julian Gonzalez
🔗 <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Download</a> | <a href="https://github.com/joticajulian/kondor">GitHub</a>
💝 <a href="https://github.com/sponsors/joticajulian">Support Julian</a>

🌐 <b>Portal Wallet</b> - <i>Web Based</i>
🖥️ No installation required
🔗 <a href="https://portal.armana.io">Access Portal</a>

👑 <b>Sovrano Wallet</b> - <i>Suggested • Active Development</i>
🔗 <a href="https://sovrano.io/">Visit Sovrano</a>

💎 <b>Tangem Wallet</b> - <i>Hardware Security</i>
🛡️ Physical card wallet
📱 iOS & Android app support
⚠️ <i>More secure but limited dApp support</i>
🔗 <a href="https://tangem.com">Learn More</a>

🔐 <b>Security Tip:</b> <i>Use multiple wallets for different purposes!</i>"""
            
        elif call.data == "international":
            text = """🌍 <b>Global Koinos Community</b>

<i>Connect with Koinos enthusiasts worldwide!</i>

🇩🇪 <a href="https://t.me/koinosgermany">Deutschland</a> - German Community
🇪🇸 <a href="https://t.me/koinoshispano">España</a> - Spanish Community  
🇨🇳 <a href="https://t.me/koinos_cn">中国</a> - Chinese Community
🇮🇹 <a href="https://t.me/+8KIVdg8vhIQ5ZGY0">Italia</a> - Italian Community
🇮🇷 <a href="https://t.me/PersianKoinos">ایران</a> - Persian Community
🇹🇷 <a href="https://t.me/+ND37ePjNlvc4NGE0">Türkiye</a> - Turkish Community
🇷🇺 <a href="https://t.me/koinosnetwork_rus">Россия</a> - Russian Community
🇳🇱 <a href="https://t.me/KoinosNederland">Nederland</a> - Dutch Community

🌟 <i>Missing your language? Help us create a new community!</i>

🤝 <b>Note:</b> <i>These are unofficial community groups</i>"""
            
        elif call.data == "social":
            text = """📱 <b>Connect With Koinos</b>

🏢 <b>Official Channels:</b>
🔮 <a href="https://twitter.com/koinosnetwork">Koinos Network</a> - Main Twitter
🏗️ <a href="https://twitter.com/TheKoinosGroup">Koinos Group</a> - Development Team
💬 <a href="https://discord.koinos.io">Discord Server</a> - Real-time chat
📝 <a href="https://medium.com/koinosnetwork">Medium Blog</a> - Deep insights
📺 <a href="https://www.youtube.com/@KoinosNetwork">YouTube Channel</a> - Video content

⚡ <b>Community Channels:</b>
📰 <a href="https://koinosnews.com/">Koinos News</a> - Latest updates
🛠️ <a href="https://www.youtube.com/@motoengineer.koinos">Motoengineer</a> - Tech tutorials
📢 <a href="https://t.me/KoinosNews">News Telegram</a> - Breaking news
🚀 <a href="https://t.me/thekoinosarmy">Koinos Army</a> - Price & trading

🌍 <i>Don't forget to check /international for local communities!</i>

💫 <b>Stay updated with the latest from Koinos!</b>"""
            
        elif call.data == "stake":
            text = """🔥 <b>Earn with Koinos Burning</b>

💰 <b>Burn $KOIN for rewards!</b>
📈 <i>Earn 4-8% APR by burning KOIN for 1 year</i>

📚 <b>Learn the Basics:</b>
🎥 <a href="https://www.youtube.com/watch?v=v9bhaNLuDms">Koinos Overview: Miners, Holders & Developers</a>

⛏️ <b>Mining Guide:</b>
🎬 <a href="https://youtu.be/pa2kSYSdVnE?si=kxX4BBbjriL29x6m">How to mine $KOIN with $VHP</a>

🖥️ <b>Run Your Own Node:</b>
📖 <a href="https://docs.koinos.io/validators/guides/running-a-node/">Node Setup Guide</a>

<b>━━━ OR JOIN A POOL ━━━</b>

🔥 <b>Staking Pools:</b>
🌋 <a href="https://fogata.io">Fogata</a> - Professional mining pool
💎 <a href="https://burnkoin.com">Burn Koin</a> - Community pool

⚡ <i>Choose your preferred way to earn with Koinos!</i>"""
            
        elif call.data == "whitepaper":
            text = """📄 <b>Koinos Documentation</b>

📚 <b>Essential Reading:</b>
📖 <a href="https://koinos.io/whitepaper/">Official Whitepaper</a> - Complete technical spec

🎙️ <b>Audio Content:</b>
🎧 <a href="https://podcast.thekoinpress.com/episodes/the-koinos-whitepaper">Koin Press Podcast</a> - Whitepaper discussion

📺 <b>Video Explanations:</b>
▶️ <a href="https://www.youtube.com/watch?v=v-qFFbDvV2c">Community Video</a> - Visual breakdown

🧠 <i>Understanding Koinos starts with the fundamentals!</i>

💡 <b>Key Concepts:</b>
• Fee-less transactions via Mana
• Universal Upgradeability  
• Proof of Burn consensus
• Developer-friendly environment"""
        
        if text:
            await bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                          parse_mode='HTML', reply_markup=create_main_menu_keyboard())
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
    
    await bot.answer_callback_query(call.id)

# --- Main Execution ---

async def main():
    logger.info("🚀 Koinos Bot starting up...")
    try:
        await bot.polling(non_stop=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Koinos Bot shutting down...")
        await bot.stop_polling()
        await bot.close_session()

if __name__ == '__main__':
    asyncio.run(main())
