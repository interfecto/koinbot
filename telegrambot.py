import asyncio
from collections import namedtuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import requests
import signal
import telebot
from telebot.async_telebot import AsyncTeleBot
import time

load_dotenv()

bot = AsyncTeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
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

def make_program_blurb(program):
    return """⚡️ <b><a href="{url}">{title}</a></b>
👉 {subtitle}
{shortDescription}""".format_map(program)

async def send_message(message, link_preview=False, html=True, chat_id=chat_id, reply_markup=None):
    return await bot.send_message(
        chat_id,
        message,
        parse_mode='html' if html else None,
        link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=not link_preview),
        reply_markup=reply_markup)


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

    await asyncio.sleep(180)
    for captcha_message in captcha_messages:
        try:
            await bot.delete_message(captcha_message.chat.id, captcha_message.id)
        except:
            pass

    async with challenge_lock:
        if user.id in active_challenges:
            del active_challenges[user.id]
            await kick_user(user)


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
@bot.message_handler(commands=['mana'])
async def hanlde_mana(message):
    await send_message("""
🔮 Mana is behind the magic of Koinos. Every KOIN inherently contains Mana, \
which is used when using the Koinos blockchain. And just like in video games, \
your Mana recharges over time letting you continue to use Koinos forever!

<a href="https://docs.koinos.io/overview/mana/">Learn more about Mana!</a>
""")


#Media Links
@bot.message_handler(commands=['media','social'])
async def handle_media(message):
    await send_message("""
🔮 <b>Official Koinos Media</b>
<a href="https://twitter.com/koinosnetwork">Koinos Network X</a>
<a href="https://twitter.com/TheKoinosGroup">Koinos Group X</a>
<a href="https://discord.koinos.io">Discord</a>
<a href="https://medium.com/koinosnetwork">Medium</a>
<a href="https://www.youtube.com/@KoinosNetwork">YouTube</a>

⚡ <b>Unofficial Koinos Media</b>
<a href="https://koinosnews.com/">Koinos News</a>
<a href="https://www.youtube.com/@motoengineer.koinos">motoengineer YouTube</a>
<a href="https://t.me/KoinosNews">Koinos News Telegram</a>
<a href="https://t.me/thekoinosarmy">Koinos Army Telegram</a>

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

@bot.message_handler(commands=['rules','guidelines'])
async def handle_rules(message):
    await send_message("""Welcome to the Koinos Telegram community!

We kindly ask you follow these guidelines to help create a positive and innovative environment.

✅ Share your projects, discuss features, plans, and seek feedback.

✅ Discuss and build dApps, features, and developments.

✅ Share constructive feedback that leads to improvement.

✅ Maintain a professional, respectful, and valuable conversations.

✅ Grow the ecosystem with insights, resources, and feedback.

✅ Avoid promoting non-utility tokens, projects, or dApps.

✅ Keep discussions on-topic and avoid unrelated content.

✅ Uphold these guidelines and foster a welcoming community.

📄 View complete guidelines \
<a href="https://docs.google.com/document/d/1-WYFlj7p3U0GG5Q5_OQPR5tzRD4WlG3FKNj4u9Lz3vQ/edit?usp=sharing">here</a>.
""")

# Start polling
async def start_polling():
    await bot.polling(non_stop=True, allowed_updates=['message','chat_member'])

# Gracefully stop polling
async def stop_polling():
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
