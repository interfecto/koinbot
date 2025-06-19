import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import requests
import telebot
from telebot.async_telebot import AsyncTeleBot
import time

load_dotenv()

bot = AsyncTeleBot(os.environ['TELEGRAM_BOT_TOKEN'])
chat_id = os.environ['CHAT_ID']
new_users = set()
new_users_lock = asyncio.Lock()

def get_programs():
    url = 'https://koinos.io/api/programs'
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

    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, selective=True)
    options = ['Koinos', 'Bitcoin', 'Chainge']
    random.shuffle(options)
    markup.add(*options)

    captcha_messages = list()

    async with new_users_lock:
        for member in message.new_chat_members:
            new_users.add(member.id)
            captcha_messages.append(await send_message(
                f"Welcome @{member.username}, what is the name of this project?", reply_markup=markup))

    await asyncio.sleep(180)
    for captcha_message in captcha_messages:
        try:
            await bot.delete_message(captcha_message.chat.id, captcha_message.id)
        except:
            pass

    async with new_users_lock:
        for member in message.new_chat_members:
            if {member.id} <= new_users:
                new_users.remove(member.id)
                await kick_user(member)

@bot.message_handler(func=lambda message: message.reply_to_message != None)
async def handle_new_user_response(message):
    async with new_users_lock:
        if not {message.from_user.id} <= new_users:
            return

        new_users.remove(message.from_user.id)

    await bot.delete_message(message.chat.id, message.reply_to_message.id)
    await bot.delete_message(message.chat.id, message.id)

    if message.text != 'Koinos':
        await kick_user(message.from_user)
        return

    await welcome_new_users([message.from_user])

async def kick_user(user):
    await bot.kick_chat_member(chat_id, user.id, until_date=datetime.today() + timedelta(days=7))

async def welcome_new_users(users):
    programs = get_programs()
    active_program_message = None
    has_program_image = False

    if len(programs) > 0:
        for program in programs:
            if not program['active']:
                continue

        active_program_message = f"""

🔮 Featured Program:

{make_program_blurb(program)}"""

        if program['images'] != None and program['images']['banner'] != None:
            has_program_image = True
            active_program_message = f"""<a href="{program['images']['banner']}">&#8205;</a>""" + active_program_message
    response = ""

    usernames =['@' + user.username for user in users]
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

    await send_message(response, link_preview=has_program_image, reply_markup=telebot.types.ReplyKeyboardRemove(selective=True))

@bot.message_handler(content_types=['left_chat_member'])
async def delete_leave_message(message):
    await bot.delete_message(message.chat.id, message.id)

#list of commands
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
# (removed koiner reference)
# If you need an alternative, you must provide another endpoint.
def get_virtual_supply():
    # url = 'https://checker.koiner.app/koin/virtual-supply'
    # response = requests.get(url)
    # data = response.json()
    # return data
    return "Unavailable (Koiner removed)"

@bot.message_handler(commands=['supply'])
async def handle_supply(message):
    data = get_virtual_supply()
    await send_message(f"""The Virtual Supply ($KOIN+$VHP) is: {data}.

For more information, read about Koinos' <a href="https://docs.koinos.io/overview/tokenomics/">tokenomics</a>!""")

#Get VHP Total Supply
# (removed koiner reference)
def get_vhp_supply():
    # url = 'https://checker.koiner.app/vhp/total-supply'
    # response = requests.get(url)
    # data = response.json()
    # return data
    return "Unavailable (Koiner removed)"

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
<a href="https://dapp.chainge.finance/?fromChain=ETH&toChain=ETH&fromToken=USDT&toToken=KOIN">Chainge</a>

🌐 <b>DEXs</b>:
<a href="https://app.uniswap.org/explore/tokens/ethereum/0xed11c9bcf69fdd2eefd9fe751bfca32f171d53ae">Uniswap</a>

📈 <b>CEXs</b>:
<a href="https://www.mexc.com/exchange/KOIN_USDT">MEXC</a>
<a href="https://bingx.com/en/spot/KOINUSDT/">BingX</a>
<a href="https://www.biconomy.com/exchange/KOIN_USDT">Biconomy</a>
<a href="https://www.coinstore.com/#/spot/KOINUSDT">Coinstore</a>
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

    message = "🔮 Koinos active programs!\n"
    image = None

    for program in programs:
        message += f"""
{make_program_blurb(program)}"""

        if image == None and program['images'] != None and program['images']['banner'] != None:
            image = program['images']['banner']

    if image != None:
        message = f"""<a href="{image}">&#8205;</a>""" + message

    await send_message(message, True)

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
    await bot.polling(non_stop=True)

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
