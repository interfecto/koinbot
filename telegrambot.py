import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import requests
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

bot = AsyncTeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
chat_id = os.environ['CHAT_ID']
new_users = set()
new_users_lock = asyncio.Lock()

# Configuration
CAPTCHA_TIMEOUT = 180  # 3 minutes
BAN_DURATION_DAYS = 7
REQUEST_TIMEOUT = 10

def get_programs():
    """Fetch programs from Koinos API with error handling"""
    try:
        url = 'https://koinos.io/api/programs'
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data.get('programs', [])
    except requests.RequestException as e:
        logger.error(f"Failed to fetch programs: {e}")
        return []

def make_program_blurb(program):
    """Create a beautifully formatted program description"""
    return f"""🚀 <b><a href="{program.get('url', '#')}">{program.get('title', 'Unknown Program')}</a></b>
✨ <i>{program.get('subtitle', '')}</i>
📝 {program.get('shortDescription', '')}"""

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

def create_back_keyboard():
    """Create a back button keyboard"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Back to Menu", callback_data="main_menu"))
    return keyboard

async def send_message(message, link_preview=False, html=True, chat_id=chat_id, reply_markup=None):
    """Enhanced message sender with error handling"""
    try:
        return await bot.send_message(
            chat_id,
            message,
            parse_mode='HTML' if html else None,
            link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=not link_preview),
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return None

async def send_loading_message(chat_id, text="🔄 Loading..."):
    """Send a loading message that can be edited later"""
    try:
        return await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Failed to send loading message: {e}")
        return None

async def edit_message_with_animation(message, final_text, reply_markup=None):
    """Edit message with a cool loading animation effect"""
    try:
        loading_frames = ["🔄", "⏳", "✨", "🚀"]
        for frame in loading_frames:
            await bot.edit_message_text(
                f"{frame} Loading...",
                message.chat.id,
                message.message_id
            )
            await asyncio.sleep(0.3)
        
        await bot.edit_message_text(
            final_text,
            message.chat.id,
            message.message_id,
            parse_mode='HTML',
            reply_markup=reply_markup,
            link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=False)
        )
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

# welcome message
@bot.message_handler(content_types=['new_chat_members'])
async def handle_welcome(message):
    await bot.delete_message(message.chat.id, message.id)
    from_user = await bot.get_chat_member(message.chat.id, message.from_user.id)

    # For testing using 'welcome'
    if message.new_chat_members == None or len(message.new_chat_members) == 0:
        message.new_chat_members = [message.from_user]
        from_user.status = ""

    if from_user.status == 'creator' or from_user.status == 'administrator':
        await welcome_new_users(message.new_chat_members)
        return

    # Modern captcha with better UX
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, selective=True, resize_keyboard=True)
    options = ['🔮 Koinos', '₿ Bitcoin', '🔷 Ethereum']
    random.shuffle(options)
    markup.add(*options)

    captcha_messages = list()

    async with new_users_lock:
        for member in message.new_chat_members:
            new_users.add(member.id)
            welcome_text = f"""🎉 <b>Welcome @{member.username}!</b>

🛡️ <i>Quick security check:</i>
What is the name of this blockchain project?

⏰ <i>You have 3 minutes to respond...</i>"""
            
            captcha_messages.append(await send_message(
                welcome_text, reply_markup=markup))

    await asyncio.sleep(CAPTCHA_TIMEOUT)
    for captcha_message in captcha_messages:
        try:
            await bot.delete_message(captcha_message.chat.id, captcha_message.id)
        except:
            pass

    async with new_users_lock:
        for member in message.new_chat_members:
            # Fixed: Use proper membership check instead of set operations
            if member.id in new_users:
                new_users.remove(member.id)
                await kick_user(member)

# Security handler: Block ALL messages from unverified users
@bot.message_handler(func=lambda message: True)
async def handle_all_messages(message):
    """Security filter: Block unverified users from sending any messages"""
    async with new_users_lock:
        # If user is in new_users set, they haven't completed captcha
        if message.from_user.id in new_users:
            # Delete their message immediately
            try:
                await bot.delete_message(message.chat.id, message.id)
            except:
                pass
            
            # If it's a reply to the captcha, handle it
            if message.reply_to_message is not None:
                await handle_captcha_response(message)
            else:
                # Not a captcha reply - warn and potentially kick for spam
                logger.warning(f"User {message.from_user.username} ({message.from_user.id}) tried to send message before completing captcha")
                
                # Optional: Kick immediately for attempting to bypass captcha
                warning_msg = await send_message(
                    f"⚠️ <b>@{message.from_user.username}</b>, please complete the security check first!"
                )
                await asyncio.sleep(3)
                try:
                    await bot.delete_message(warning_msg.chat.id, warning_msg.message_id)
                except:
                    pass
            
            return  # Don't process any other handlers
    
    # User is verified, allow normal message processing
    # (Other message handlers will process this message)

async def handle_captcha_response(message):
    """Handle captcha responses from new users"""
    async with new_users_lock:
        # Double-check user is still in new_users
        if message.from_user.id not in new_users:
            return

        new_users.remove(message.from_user.id)

    # Delete the captcha message and user's response
    try:
        await bot.delete_message(message.chat.id, message.reply_to_message.id)
        await bot.delete_message(message.chat.id, message.id)
    except:
        pass

    # Check for correct answer (flexible matching)
    correct_answers = ['🔮 Koinos', 'Koinos', 'koinos', 'KOINOS']
    if message.text not in correct_answers:
        # Send a nice goodbye message before kicking
        goodbye_msg = await send_message(
            f"❌ <b>Incorrect answer, @{message.from_user.username}</b>\n\n"
            f"🚪 <i>Please try again when you're ready to join our community!</i>"
        )
        await asyncio.sleep(2)
        try:
            await bot.delete_message(goodbye_msg.chat.id, goodbye_msg.message_id)
        except:
            pass
        await kick_user(message.from_user)
        return

    # Correct answer - welcome the user
    await welcome_new_users([message.from_user])

async def kick_user(user):
    """Kick user with enhanced logging"""
    try:
        await bot.kick_chat_member(chat_id, user.id, until_date=datetime.today() + timedelta(days=BAN_DURATION_DAYS))
        logger.info(f"Kicked user {user.username} ({user.id}) for failing captcha")
    except Exception as e:
        logger.error(f"Failed to kick user {user.username}: {e}")

async def welcome_new_users(users):
    """Enhanced welcome message with modern design"""
    programs = get_programs()
    active_program_message = None
    has_program_image = False

    # Fixed: Properly find active program and break after finding one
    active_program = None
    if len(programs) > 0:
        for program in programs:
            if program.get('active', False):
                active_program = program
                break

    if active_program:
        active_program_message = f"""

🌟 <b>Featured Program:</b>

{make_program_blurb(active_program)}"""

        if (active_program.get('images') and 
            active_program['images'].get('banner')):
            has_program_image = True
            active_program_message = f"""<a href="{active_program['images']['banner']}">&#8205;</a>""" + active_program_message

    # Create beautiful username list
    usernames = [f'@{user.username}' if user.username else f'User{user.id}' for user in users]
    if len(usernames) > 1:
        usernames[-1] = 'and ' + usernames[-1]

    username_list = ', '.join(usernames) if len(usernames) > 2 else ' '.join(usernames)

    response = f"""🎉 <b>Welcome {username_list}!</b>

🚀 <i>Ready to explore the future of blockchain?</i>

💡 <b>Getting Started:</b>
• Check out our current /programs
• Review our community /rules  
• Explore /projects in our ecosystem

❓ <b>Need help?</b> Feel free to ask questions!"""

    if active_program_message:
        response += active_program_message

    response += """

🛡️ <b>Security Reminder:</b>
• Admins will <u>never</u> DM you first
• We'll <u>never</u> ask for keys or seed phrases
• Suspicious behavior? Use /report

<i>Welcome to the Koinos community! 🔮</i>"""

    await send_message(
        response, 
        link_preview=has_program_image, 
        reply_markup=telebot.types.ReplyKeyboardRemove(selective=True)
    )

@bot.message_handler(content_types=['left_chat_member'])
async def delete_leave_message(message):
    """Clean up leave messages"""
    await bot.delete_message(message.chat.id, message.id)

# Enhanced help command with modern design
@bot.message_handler(commands=['help', 'start', 'menu'])
async def send_help(message):
    """Modern help command with inline keyboard navigation"""
    help_text = """🔮 <b>Welcome to Koinos Bot!</b>

🎯 <b>Your gateway to the Koinos ecosystem</b>

<i>Use the buttons below to navigate, or type commands directly:</i>

🔥 <b>Quick Commands:</b>
/claim - Token claiming info
/price - Price discussion rules  
/supply - Token supply info
/mana - Learn about Mana
/roadmap - Development roadmap
/rules - Community guidelines

💫 <i>Choose an option below to get started!</i>"""
    
    await send_message(help_text, reply_markup=create_main_menu_keyboard())

# Callback query handler for inline keyboards
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback_query(call):
    """Handle all inline keyboard callbacks with loading animations"""
    loading_msg = await send_loading_message(call.message.chat.id)
    
    try:
        if call.data == "main_menu":
            help_text = """🔮 <b>Welcome to Koinos Bot!</b>

🎯 <b>Your gateway to the Koinos ecosystem</b>

<i>Use the buttons below to navigate, or type commands directly:</i>

🔥 <b>Quick Commands:</b>
/claim - Token claiming info
/price - Price discussion rules  
/supply - Token supply info
/mana - Learn about Mana
/roadmap - Development roadmap
/rules - Community guidelines

💫 <i>Choose an option below to get started!</i>"""
            await edit_message_with_animation(loading_msg, help_text, create_main_menu_keyboard())
            
        elif call.data == "guides":
            await handle_guides_callback(loading_msg)
        elif call.data == "projects":
            await handle_projects_callback(loading_msg)
        elif call.data == "exchanges":
            await handle_exchanges_callback(loading_msg)
        elif call.data == "wallets":
            await handle_wallets_callback(loading_msg)
        elif call.data == "international":
            await handle_international_callback(loading_msg)
        elif call.data == "social":
            await handle_media_callback(loading_msg)
        elif call.data == "stake":
            await handle_stake_callback(loading_msg)
        elif call.data == "whitepaper":
            await handle_whitepaper_callback(loading_msg)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await bot.edit_message_text("❌ Something went wrong. Please try again.", loading_msg.chat.id, loading_msg.message_id)
    
    # Answer the callback query
    await bot.answer_callback_query(call.id)

async def handle_guides_callback(message):
    """Enhanced guides with modern formatting"""
    text = """📚 <b>Koinos Learning Hub</b>

🎓 <b>Official Documentation:</b>
📖 <a href="https://docs.koinos.io">Complete Koinos Docs</a>

⚡ <b>Core Concepts:</b>
🔮 <a href="https://docs.koinos.io/overview/mana/">Master Mana Mechanics</a>

💡 <i>Start your Koinos journey with these essential guides!</i>"""
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_projects_callback(message):
    """Enhanced projects list with categories"""
    text = """🚀 <b>Koinos Ecosystem Projects</b>

📱 <b>dApps & Platforms:</b>
🎨 <a href="https://kollection.app">Kollection</a> - NFT Marketplace
🏙️ <a href="https://koincity.com">Koincity</a> - Virtual World
📝 <a href="https://koinosbox.com/nicknames">Nicknames</a> - Name Service
🖼️ <a href="https://kanvas-app.com">Kanvas</a> - Creative Platform
🌱 <a href="https://koinosgarden.com">Koinos Garden</a> - DeFi

🎮 <b>Gaming:</b>
⚔️ <a href="https://www.lordsforsaken.com/">Lord's Forsaken</a> - Strategy Game
🚀 <a href="https://planetkoinos.com/space_striker.html">Space Striker</a> - Action Game

⛏️ <b>Mining & Staking:</b>
🔥 <a href="https://fogata.io">Fogata</a> - Mining Pool
💎 <a href="https://burnkoin.com">Burn Koin</a> - Staking Pool

🔍 <b>Infrastructure:</b>
📊 <a href="https://koinosblocks.com">KoinosBlocks</a> - Block Explorer

💳 <b>Wallets:</b>
🦊 <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Kondor</a> - Browser Extension
📱 <a href="https://konio.io">Konio</a> - Mobile Wallet
🌐 <a href="https://portal.armana.io">Portal</a> - Web Wallet

🤖 <b>AI & Tools:</b>
🧠 <a href="https://planetkoinos.com/koinos_ai.html">Koinos AI</a> - AI Assistant

🌟 <i>The ecosystem is growing daily!</i>"""
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_exchanges_callback(message):
    """Enhanced exchanges with modern categorization"""
    text = """💱 <b>Trade $KOIN Everywhere</b>

🌐 <b>Decentralized Exchanges:</b>
🦄 <a href="https://app.uniswap.org/explore/tokens/ethereum/0xed11c9bcf69fdd2eefd9fe751bfca32f171d53ae">Uniswap</a> - Leading DEX

📈 <b>Centralized Exchanges:</b>
🏪 <a href="https://www.mexc.com/exchange/KOIN_USDT">MEXC</a> - Global Exchange
⚡ <a href="https://bingx.com/en/spot/KOINUSDT/">BingX</a> - Crypto Trading
💼 <a href="https://www.biconomy.com/exchange/KOIN_USDT">Biconomy</a> - Digital Assets
🏬 <a href="https://www.coinstore.com/#/spot/KOINUSDT">Coinstore</a> - Trading Platform
🇪🇺 <a href="https://exchange.lcx.com/trade/KOIN-EUR">LCX</a> - European Exchange

🔥 <b>More listings coming soon!</b>
<i>We're always working on new exchange partnerships</i>

⚠️ <i>Free to request exchanges, but no guarantees on timing!</i>"""
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_wallets_callback(message):
    """Enhanced wallet information"""
    text = """💳 <b>Secure Your $KOIN</b>

<i>Choose the perfect wallet for your needs:</i>

🦊 <b>Kondor Wallet</b> - <i>Most Popular</i>
💻 Browser extension for Chrome & Brave
👨‍💻 Created by Julian Gonzalez
🔗 <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Download</a> | <a href="https://github.com/joticajulian/kondor">GitHub</a>
💝 <a href="https://github.com/sponsors/joticajulian">Support Julian</a>

📱 <b>Konio Wallet</b> - <i>Mobile First</i>
📲 iOS & Android native app
👨‍💻 Created by Adriano Foschi  
🔗 <a href="https://konio.io">Download</a> | <a href="https://github.com/konio-io/konio-mobile">GitHub</a>

🌐 <b>Portal Wallet</b> - <i>Web Based</i>
🖥️ No installation required
🔗 <a href="https://portal.armana.io">Access Portal</a>

💎 <b>Tangem Wallet</b> - <i>Hardware Security</i>
🛡️ Physical card wallet
📱 iOS & Android app support
⚠️ <i>More secure but limited dApp support</i>
🔗 <a href="https://tangem.com">Learn More</a>

🔐 <b>Security Tip:</b> <i>Use multiple wallets for different purposes!</i>"""
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_international_callback(message):
    """Enhanced international communities"""
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
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_media_callback(message):
    """Enhanced social media links"""
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
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_stake_callback(message):
    """Enhanced staking information"""
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
    
    await edit_message_with_animation(message, text, create_back_keyboard())

async def handle_whitepaper_callback(message):
    """Enhanced whitepaper section"""
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
    
    await edit_message_with_animation(message, text, create_back_keyboard())

#report
@bot.message_handler(commands=['report'])
async def send_report(message):
    """Enhanced report command with better formatting"""
    report_text = """🚨 <b>ADMIN ALERT</b> 🚨

<b>Someone needs attention from moderators:</b>
@kuixihe @weleleliano @saleh_hawi @fifty2kph

⚠️ <i>Reported by:</i> @{username}
🕐 <i>Time:</i> {time}""".format(
        username=message.from_user.username or f"User{message.from_user.id}",
        time=datetime.now().strftime("%H:%M:%S")
    )
    
    await send_message(report_text)

#website
@bot.message_handler(commands=['website', 'websites'])
async def send_website(message):
    """Enhanced website command"""
    await send_message(
        '🌐 <b><a href="https://koinos.io">Visit Koinos.io</a></b>\n\n'
        '✨ <i>Discover the future of blockchain technology!</i>', 
        True
    )

#stake
@bot.message_handler(commands=['stake'])
async def send_stake(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#whitepaper
@bot.message_handler(commands=['whitepaper'])
async def send_whitepaper(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Get KOIN Virtual Supply
# (removed koiner reference)
# If you need an alternative, you must provide another endpoint.
def get_virtual_supply():
    # url = 'https://checker.koiner.app/koin/virtual-supply'
    # response = requests.get(url)
    # data = response.json()
    # return data
    return "🔄 <i>Data source updating...</i>"

@bot.message_handler(commands=['supply'])
async def handle_supply(message):
    """Enhanced supply command with modern formatting"""
    data = get_virtual_supply()
    await send_message(f"""📊 <b>KOIN Virtual Supply</b>

💰 <b>Current Supply:</b> {data}
<i>(KOIN + VHP combined)</i>

📈 <b>Learn More:</b>
🔗 <a href="https://docs.koinos.io/overview/tokenomics/">Koinos Tokenomics</a>

💡 <i>Virtual supply includes both circulating KOIN and burned VHP tokens</i>""")

#Get VHP Total Supply
# (removed koiner reference)
def get_vhp_supply():
    # url = 'https://checker.koiner.app/vhp/total-supply'
    # response = requests.get(url)
    # data = response.json()
    # return data
    return "🔄 <i>Data source updating...</i>"

@bot.message_handler(commands=['vhpsupply'])
async def handle_vhp_supply(message):
    """Enhanced VHP supply command"""
    data = get_vhp_supply()
    await send_message(f"""⚡ <b>VHP Total Supply</b>

🔥 <b>Current VHP Supply:</b> {data}

📈 <b>Learn More:</b>
🔗 <a href="https://docs.koinos.io/overview/tokenomics/">Koinos Tokenomics</a>

💡 <i>VHP (Virtual Hash Power) is created by burning KOIN tokens</i>""")

#link to Koinos Forum Guides#
@bot.message_handler(commands=['guides', 'docs'])
async def handle_guides(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Link to Various social groups
@bot.message_handler(commands=['international'])
async def handle_international(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

@bot.message_handler(commands=['exchange','exchanges','cex','buy'])
async def handle_exchanges(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Mana Descriptor - Fixed typo in function name
@bot.message_handler(commands=['mana'])
async def handle_mana(message):
    """Enhanced mana explanation with modern formatting"""
    await send_message("""🔮 <b>The Magic of Mana</b>

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

#Media Links
@bot.message_handler(commands=['media','social'])
async def handle_media(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Listing of Koinos Projects
@bot.message_handler(commands=['projects'])
async def handle_projects(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Link to Koinos Roadmap
@bot.message_handler(commands=['roadmap'])
async def handle_roadmap(message):
    """Enhanced roadmap command"""
    await send_message("""🗺️ <b>Koinos Development Roadmap</b>

🚀 <b>Track our progress:</b>
📍 <a href="https://koinos.io/#roadmap">Official Koinos Roadmap</a>

🎯 <b>What's Coming:</b>
• Enhanced developer tools
• Ecosystem expansion  
• Performance optimizations
• New partnership integrations

⚡ <i>The future of blockchain is being built daily!</i>""")

#Link to price chat and MEXC
@bot.message_handler(commands=['price'])
async def handle_price(message):
    """Enhanced price command with better formatting"""
    await send_message("""📈 <b>Price Discussion Guidelines</b>

🚨 <b>Keep price talk out of this group!</b>

💬 <b>Price Discussions:</b>
🚀 <a href="https://t.me/thekoinosarmy">Koinos Army Telegram</a>

📊 <b>Live Price Data:</b>
📈 <a href="https://www.coingecko.com/en/coins/koinos">CoinGecko KOIN Price</a>

💡 <i>This channel focuses on technology, development, and community!</i>""")

#Provides information about Koinos Wallets
@bot.message_handler(commands=['wallets'])
async def handle_wallets(message):
    """This is handled by the callback system now, redirect to main menu"""
    await send_help(message)

#Give Claim Information
@bot.message_handler(commands=['claim'])
async def handle_claim(message):
    """Enhanced claim information with modern design"""
    await send_message("""🎁 <b>Token Claim Information</b>

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

@bot.message_handler(commands=['programs'])
async def handle_programs(message):
    """Enhanced programs command with loading animation"""
    loading_msg = await send_loading_message(message.chat.id, "🔍 Fetching active programs...")
    
    programs = get_programs()

    if len(programs) == 0:
        await bot.edit_message_text(
            "🚨 <b>No Active Programs</b>\n\n<i>Check back soon for exciting new opportunities!</i>",
            loading_msg.chat.id,
            loading_msg.message_id,
            parse_mode='HTML'
        )
        return

    response = "🚀 <b>Active Koinos Programs!</b>\n\n"
    image = None

    for program in programs:
        if program.get('active', False):
            response += f"{make_program_blurb(program)}\n\n"
            
            if image is None and program.get('images') and program['images'].get('banner'):
                image = program['images']['banner']

    response += "✨ <i>Join the revolution and get involved!</i>"

    if image:
        response = f'<a href="{image}">&#8205;</a>' + response

    await bot.edit_message_text(
        response,
        loading_msg.chat.id,
        loading_msg.message_id,
        parse_mode='HTML',
        link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=False)
    )

@bot.message_handler(commands=['rules','guidelines'])
async def handle_rules(message):
    """Enhanced rules with modern formatting and emojis"""
    await send_message("""🛡️ <b>Koinos Community Guidelines</b>

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

# Start polling
async def start_polling():
    logger.info("🚀 Koinos Bot starting up...")
    await bot.polling(non_stop=True)

# Gracefully stop polling
async def stop_polling():
    logger.info("🛑 Koinos Bot shutting down...")
    await bot.stop_polling()  # This will stop the polling process
    await bot.close_session()  # Close the bot's aiohttp session

async def main():
    try:
        await start_polling()
    except (KeyboardInterrupt, SystemExit):
        print("Gracefully stopping the bot...")
        await stop_polling()

if __name__ == '__main__':
    asyncio.run(main())
