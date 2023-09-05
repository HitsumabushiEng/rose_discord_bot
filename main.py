#########################################
# TODO LIST
#
#   ・Bot書き込み用Ch名を変更できるようにする?
#   ・クラス化して整理したい。
#   ・うさぎの来る時間を調べる
#   ・imgのリンクが貼られたときの動作を修正する。
#   ・うさぎさんタスクのSeqを辞書化
#   ・sqlの要素名を辞書化
#   ・次にウサギが来る時間が24時間を超える場合の処理
#   ・ウサギさん来る時間のリスト化
#   ・ウサギさんタイマー表示用チャンネル別に分ける?
#

import os
import discord
from discord.ext import commands

from myLib.L2_SystemIO.sql import SQL
import myLib.L2_SystemIO.discordIO as cogs
import myLib.L1_Apps.setting as g

#########################################
DEBUG_MODE = "Earnest_dev"
# DEBUG_MODE = "Rose_dev"
# DEBUG_MODE = "Deploy"

# TOKENの設定
match DEBUG_MODE:
    case "Deploy":
        TOKEN = os.getenv("TOKEN")
    case "Rose_dev":
        tObj = open("token")  # for Rose
        TOKEN = tObj.read()
    case "Earnest_dev":
        tObj = open("token_dev")  # for Earnest
        TOKEN = tObj.read()
    case _:
        tObj = open("token_dev")  # for Earnest
        TOKEN = tObj.read()

# DBの初期化
SQL.init()

# Clientの設定
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
client = commands.Bot(command_prefix=g.BOT_PREFIX, intents=intents)

################TEMP###############
cogs.setClient(client)
################TEMP###############


# イベントリスナーの登録
@client.event
async def setup_hook():
    await client.add_cog(cogs.General(client))
    await client.add_cog(cogs.AutoPin(client))
    await client.add_cog(cogs.BunnyTimer(client))


# クライアント起動
client.run(TOKEN)
