import asyncio
<<<<<<< HEAD
import logging
=======
from collections import namedtuple
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc
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
<<<<<<< HEAD
new_users = set()
new_users_lock = asyncio.Lock()

# Configuration
CAPTCHA_TIMEOUT = 180  # 3 minutes
BAN_DURATION_DAYS = 7
REQUEST_TIMEOUT = 10
=======
chat_id = os.environ['CHAT_ID']
koinos_io_url = os.environ['KOINOS_IO_URL']
active_challenges = dict()
challenge_lock = asyncio.Lock()
challenge = False
welcome = True

def get_programs():
    url = f'{koinos_io_url}/api/programs'
    response = requests.get(url)
    data = response.json()
    return data['programs']
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc

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

<<<<<<< HEAD
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
=======

# Handle new member
@bot.chat_member_handler()
async def handle_member(member_update):
    # If the user is not a member, this cannot be a join update
    if member_update.new_chat_member.status != 'member':
        return

    # If the user's old status is not left or kicked, this cannot be a join update
    old_status = member_update.old_chat_member.status
    if old_status != 'left' and old_status != 'kicked':
        return

    # If the from user is the chat owner or an admin, don't display the challenge, just the welcome message
    from_user = await bot.get_chat_member(chat_id, member_update.from_user.id)
    if from_user.status == 'creator' or from_user.status == 'administrator' or not challenge:
        if member_update.new_chat_member.user.username != None:
            await welcome_new_users([f'@{member_update.new_chat_member.user.username}'])
        elif member_update.new_chat_member.user.first_name != None:
            await welcome_new_users([member_update.new_chat_member.user.first_name])
        return

    await challenge_user(member_update.new_chat_member.user)


# Welcome command for admin manual welcome
@bot.message_handler(commands=['welcome'])
async def handle_welcome(message):
    global welcome

    from_user = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if from_user.status != 'creator' and from_user.status != 'administrator':
        await send_message('Only an admin can use the welcome command')
        return

    if message.text == "/welcome on":
        await send_message("Welcome message is on")
        welcome = True
        return
    elif message.text == "/welcome off":
        await send_message("Welcome message is off")
        welcome = False
        return
    elif message.text == "/welcome":
        message = 'An admin can set the welcome to on or off with /welcome [on,off].\nWelcome message is '

        if welcome:
            message += 'on.'
        else:
            message += 'off.'

        await send_message(message)
        return

    await bot.delete_message(message.chat.id, message.id)

    usernames = []

    for entity in message.entities:
        if entity.type != 'mention':
            continue

        usernames.append(message.text[slice(entity.offset, entity.offset + entity.length)])

    await welcome_new_users(usernames, True)


# Deletes joined message
@bot.message_handler(content_types=['new_chat_members'])
async def handle_new_users(message):
    await bot.delete_message(message.chat.id, message.id)


# Challenge command for testing
#@bot.message_handler(commands=['test_challenge'])
#async def handle_challenge(message):
#    await challenge_user(message.from_user)


@bot.message_handler(commands=['challenge'])
async def handle_challenge(message):
    global challenge
    from_user = await bot.get_chat_member(message.chat.id, message.from_user.id)

    if from_user.status != 'creator' and from_user.status != 'administrator':
        await send_message('Only an admin can change the challenge setting')
        return

    if message.text == '/challenge on':
        challenge = True
        await send_message('User challenge is on.')
    elif message.text == '/challenge off':
        challenge = False
        await send_message('User challenge is off.')
    else:
        message = 'An admin can set challenge to on or off with /challenge [on,off].\nUser challenge is '

        if challenge:
            message += 'on.'
        else:
            message += 'off.'

        await send_message(message)


# Create user challenge
async def challenge_user(user):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, selective=True)
    options = ['Koinos', 'Bitcoin', 'Chainge']
    random.shuffle(options)
    markup.add(*options)

    captcha_messages = list()

    async with challenge_lock:
        name = ""

        if user.username != None:
            name = f" @{user.username}"
        elif user.first_name != None:
            name = " " + user.first_name

        captcha_message = await send_message(f"Welcome{name}, what is the name of this project?", reply_markup=markup)

        captcha_messages.append( captcha_message )
        active_challenges[user.id] = captcha_message.id
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc

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

<<<<<<< HEAD
    async with new_users_lock:
        for member in message.new_chat_members:
            if member.id in new_users:
                new_users.remove(member.id)
                await kick_user(current_chat_id, member)
=======
    async with challenge_lock:
        if user.id in active_challenges:
            del active_challenges[user.id]
            await kick_user(user)
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc

@bot.message_handler(commands=['info', 'start', 'menu'])
async def send_info(message):
    """Displays the main info menu and deletes the user's command."""
    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.warning(f"Could not delete command message: {e}")
        
    help_text = """🔮 <b>Welcome to Koinos Bot!</b>

<<<<<<< HEAD
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

=======
# Handle user challenge
@bot.message_handler(func=lambda message: message.reply_to_message != None)
async def handle_new_user_response(message):
    async with challenge_lock:
        print( active_challenges )
        if message.from_user.id not in active_challenges:
            return

        if message.reply_to_message.id != active_challenges[message.from_user.id]:
            return

        del active_challenges[message.from_user.id]

    await bot.delete_message(message.chat.id, message.reply_to_message.id)
    await bot.delete_message(message.chat.id, message.id)

    if message.text != 'Koinos':
        await kick_user(message.from_user)
        return

    if message.from_user.username != None:
        await welcome_new_users([f'@{message.from_user.username}'])
    elif message.from_user.first_name != None:
        await welcome_new_users([message.from_user.first_name])


# Kick user
async def kick_user(user):
    await bot.kick_chat_member(chat_id, user.id, until_date=datetime.today() + timedelta(days=7) )


# User welcome message
async def welcome_new_users(usernames, force=False):
    global welcome
    if not welcome and not force:
        return

    programs = get_programs()
    active_program_message = None
    has_program_image = False

    if len(programs) > 0:
        for program in programs:
            if not program['featured']:
                continue

            active_program_message = f"""

🔮 Featured Program:

{make_program_blurb(program)}"""

            if program['images'] != None and program['images']['banner'] != None:
                has_program_image = True
                active_program_message = f"""<a href="{program['images']['banner']}">&#8205;</a>""" + active_program_message

    response = ""

    if len(usernames) > 1:
        usernames[-1] = 'and ' + usernames[-1]

    username_list = ''
    if len(usernames) > 2:
        username_list = ', '.join(usernames)
    else:
        username_list = ' '.join(usernames)

    response = f"""Welcome {username_list}!

To get started, we recommend you take a look at current /programs and take a moment to review the /rules.

Please feel free to ask questions!"""

    if active_program_message != None:
        response += active_program_message

    response += """

🚨 Remember: Admins will never DM you first. They will never ask for your keys or seed phrase. \
If you suspect someone is impersonating an admin, please /report them.
"""

    welcome_message = await send_message(response, link_preview=has_program_image, reply_markup=telebot.types.ReplyKeyboardRemove(selective=True))

    await asyncio.sleep(180)
    await bot.delete_message(welcome_message.chat.id, welcome_message.id)


# Handle user leaving messager
@bot.message_handler(content_types=['left_chat_member'])
async def delete_leave_message(message):
    await bot.delete_message(message.chat.id, message.id)


# List commands
@bot.message_handler(commands=['help'])
async def send_help(message):
    await send_message("""
You may use the following Commands:
/claim
/guides
/exchanges
/international
/price
/programs
/projects
/roadmap
/rules
/social
/stake
/supply
/vhpsupply
/wallets
/website
/whitepaper
""")

#report
@bot.message_handler(commands=['report'])
async def send_report(message):
    await send_message("""
Admins, someone needs to be banned
@kuixihe @weleleliano @saleh_hawi @fifty2kph
""")


#website
@bot.message_handler(commands=['website', 'websites'])
async def send_website(message):
    await send_message('<a href="https://koinos.io">Koinos Website</a>', True)


#stake
@bot.message_handler(commands=['stake'])
async def send_stake(message):
    await send_message("""
🔥 Burn KOIN (similar to staking) for 1 year and earn 4-8% APR!

❗ <a href="https://www.youtube.com/watch?v=v9bhaNLuDms">Koinos Overview: Miners, Holders, and Developers</a>

⛏️ <a href="https://youtu.be/pa2kSYSdVnE?si=kxX4BBbjriL29x6m">How to mine $KOIN with $VHP</a>

⌨️ <a href="https://docs.koinos.io/validators/guides/running-a-node/">Run your own node</a>

<b>--or--</b>

🔥 Join a Pool!
<a href="https://fogata.io">Fogata</a>
<a href="https://burnkoin.com">Burn Koin</a>
""")

#whitepaper
@bot.message_handler(commands=['whitepaper'])
async def send_whitepaper(message):
    await send_message("""
📄 <a href="https://koinos.io/whitepaper/">Official Whitepaper</a>

🎤️ <a href="https://podcast.thekoinpress.com/episodes/the-koinos-whitepaper">Koin Press PodCast on White Paper</a>

▶️ <a href="https://www.youtube.com/watch?v=v-qFFbDvV2c">Community Member Video</a>
""")


#Get KOIN Virtual Supply
def get_virtual_supply():
    url = 'https://checker.koiner.app/koin/virtual-supply'
    response = requests.get(url)
    data = response.json()
    return data


@bot.message_handler(commands=['supply'])
async def handle_supply(message):
    data = get_virtual_supply()
    await send_message(f"""The Virtual Supply ($KOIN+$VHP) is: {data}.

For more information, read about Koinos' <a href="https://docs.koinos.io/overview/tokenomics/">tokenomics</a>!""")


#Get VHP Total Supply
def get_vhp_supply():
    url = 'https://checker.koiner.app/vhp/total-supply'
    response = requests.get(url)
    data = response.json()
    return data


@bot.message_handler(commands=['vhpsupply'])
async def handle_vhp_supply(message):
    data = get_vhp_supply()
    await send_message(f"""The Total Supply of $VHP is: {data}.

For more information, read about Koinos' <a href="https://docs.koinos.io/overview/tokenomics/">tokenomics</a>!""")


#link to Koinos Forum Guides#
@bot.message_handler(commands=['guides', 'docs'])
async def handle_guides(message):
    await send_message("""
📄 <a href="https://docs.koinos.io">Official Koinos documentation</a>

🌁 <a href="https://www.youtube.com/watch?v=UFniurcWDcM">How to bridge with Chainge Finance</a>

🔮 <a href="https://docs.koinos.io/overview/mana/">Everything you need to know about Mana</a>
""")


#Link to Various social groups
@bot.message_handler(commands=['international'])
async def handle_international(message):
    await send_message("""🌍 Unofficial International Groups 🌏

🇩🇪 <a href="https://t.me/koinosgermany">Deutsch</a>
🇪🇸 <a href="https://t.me/koinoshispano">Español</a>
🇨🇳 <a href="https://t.me/koinos_cn">中文</a>
🇮🇹 <a href="https://t.me/+8KIVdg8vhIQ5ZGY0">Italiano</a>
🇮🇷 <a href="https://t.me/PersianKoinos">Persian</a>
🇹🇷 <a href="https://t.me/+ND37ePjNlvc4NGE0">Turkish</a>
🇷🇺 <a href="https://t.me/koinosnetwork_rus">Russian</a>
🇳🇱 <a href="https://t.me/KoinosNederland">Dutch</a>
""")


@bot.message_handler(commands=['exchange','exchanges','cex','buy'])
async def handle_exchanges(message):
    await send_message("""🔮 $KOIN is supported on the following exchanges

🌁 <b>Bridges</b>:
<a href="https://dapp.chainge.finance/?fromChain=ETH&toChain=KOIN&fromToken=USDT&toToken=KOIN">Chainge</a>

🌐 <b>DEXs</b>:
<a href="https://app.uniswap.org/explore/tokens/ethereum/0xed11c9bcf69fdd2eefd9fe751bfca32f171d53ae">Uniswap</a>
<a href="https://app.koindx.com/swap">KoinDX</a>

📈 <b>CEXs</b>:
<a href="https://www.mexc.com/exchange/KOIN_USDT">MEXC</a>
<a href="https://bingx.com/en/spot/KOINUSDT/">BingX</a>
<a href="https://exchange.lcx.com/trade/KOIN-EUR">LCX</a>

🚨 Exchange Listings are always being pursued! We cannot discuss potential or in progress listings. \
You are free to request specific exchanges but do not be disappointed when you do not receive a response.
""")

#Mana Descriptor
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc
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

<<<<<<< HEAD
💫 <i>Welcome to fee-less blockchain interactions!</i>""")
=======
Also check out /international for international communities!
""")


#Listing of Koinos Projects
@bot.message_handler(commands=['projects'])
async def handle_projects(message):
    await send_message("""
🔮 Existing Koinos Projects 🔮

📄 <b>dApps:</b>
<a href="https://koindx.com">KoinDX</a>
<a href="https://kollection.app">Kollection</a>
<a href="https://koincity.com">Koincity</a>
<a href="https://koinosbox.com/nicknames">Nicknames</a>
<a href="https://kanvas-app.com">Kanvas</a>
<a href="https://koinosgarden.com">Koinos Garden</a>

🎮 <b>Games:</b>
<a href="https://www.lordsforsaken.com/">Lord's Forsaken</a>
<a href="https://planetkoinos.com/space_striker.html">Space Striker</a>

⛏️ <b>Mining Pools:</b>
<a href="https://fogata.io">Fogata</a>
<a href="https://burnkoin.com">Burn Koin</a>

🔍 <b>Block Explorers:</b>
<a href="https://koiner.app">Koiner</a>
<a href="https://koinosblocks.com">KoinosBlocks</a>

💳 <b>Wallets:</b>
<a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Kondor</a>
<a href="https://konio.io">Konio</a>
<a href="https://portal.armana.io">Portal</a>

💻 <b>Misc:</b>
<a href="https://planetkoinos.com/koinos_ai.html">Koinos AI</a>
""")


#Link to Koinos Roadmap
@bot.message_handler(commands=['roadmap'])
async def handle_roadmap(message):
   await send_message("""
📍 <a href="https://koinos.io/#roadmap">The official Koinos Network roadmap</a>
""")


#Link to price chat and MEXC
@bot.message_handler(commands=['price'])
async def handle_price(message):
    await send_message("""🚨 Please keep price chats out of this group. \
To talk about price, please visit the <a href="https://t.me/thekoinosarmy">Koinos Army Telegram</a>!

💵 Find the price of $KOIN on <a href="https://www.coingecko.com/en/coins/koinos">CoinGecko</a>.""")


#Provides information about Koinos Wallets
@bot.message_handler(commands=['wallets'])
async def handle_wallets(message):
    await send_message("""💳 These are the recommended wallets to use with Koinos! \
Choose one or use a combination for security and accessibility!

⚡️ <a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl"><b>Kondor Wallet</b></a>
💻 Browser extension wallet for Chrome and Brave
Created by Julian Gonzalez
<a href="https://github.com/joticajulian/kondor">Kondor Github</a>
<a href="https://github.com/sponsors/joticajulian">Sponsor Julian</a>

⚡️ <a href="https://konio.io"><b>Konio Wallet</b></a>
📱 Mobile Wallet for iOS & Android
Created by Adriano Foschi
<a href="https://github.com/konio-io/konio-mobile">Koinio Github</a>

⚡️ <a href="https://tangem.com"><b>Tangem Wallet</b></a>
📱 Hardware Wallet for iOS & Android
More secure but less dApp support
""")


#Give Claim Information
@bot.message_handler(commands=['claim'])
async def handle_claim(message):
    await send_message("""

⚠️ Claim information ⚠️

⚡️ You are only eligible if you held your ERC-20 KOIN token during the snapshot. \
To verify, find your wallet address in this <a href="https://t.me/koinos_community/109226">snapshot record</a>.

⚡️ You will need a Koinos Wallet to hold your main net $KOIN tokens! Use \
<a href="https://chrome.google.com/webstore/detail/kondor/ghipkefkpgkladckmlmdnadmcchefhjl">Kondor</a> to manage your $KOIN.

🚨 SAVE YOUR PRIVATE KEYS OR SEED PHRASES!!! 🚨

🚨 Seriously, did you back up your private key or seed phrase? We cannot recover them if you lose them.

▶️ <a href="https://youtu.be/l-5dHGqUSj4">Video Tutorial on how to claim.</a>

📄 <a href="https://medium.com/@kuixihe/a-complete-guide-to-claiming-koin-tokens-edd20e7d9c40">Document tutorial on how to claim.</a>

⚡️ There is no time limit to claiming. You may claim at any time!
""")

@bot.message_handler(commands=['programs'])
async def handle_programs(message):
    programs = get_programs()

    if len(programs) == 0:
        await send_message("🚨 There are no active programs at this time.")
        return

    messageEntry = namedtuple("messageEntry", ["message", "has_image"])
    messages = []

    for program in programs:
        has_image = False

        message = f"""{make_program_blurb(program)}"""

        if program['images'] != None and program['images']['banner'] != None:
            has_image = True
            message = f"""<a href="{program['images']['banner']}">&#8205;</a>""" + message

        if program['featured']:
            messages.insert(0, messageEntry(message, has_image))
        else:
            messages.append(messageEntry(message, has_image))

    for entry in messages:
        await send_message(entry.message, entry.has_image)
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc

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

<<<<<<< HEAD
📚 <b>Step-by-Step Guides:</b>
📺 <a href="https://youtu.be/l-5dHGqUSj4">Video Tutorial</a>
📖 <a href="https://medium.com/@kuixihe/a-complete-guide-to-claiming-koin-tokens-edd20e7d9c40">Written Guide</a>
=======
# Start polling
async def start_polling():
    await bot.polling(non_stop=True, allowed_updates=['message','chat_member'])
>>>>>>> 4bb321840685346b26a683b191285a0b0b8d1fcc

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
