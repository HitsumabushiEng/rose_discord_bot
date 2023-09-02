import discord
from zoneinfo import ZoneInfo
from datetime import time


#########################################
# USER 環境変数の設定
KEYWORDS_PIN = ["📌", "📍"]
KEYWORDS_CHECK = ["✅", "☑️", "✔️"]
EMOJI_CHECK = [discord.partial_emoji.PartialEmoji.from_str(s) for s in KEYWORDS_CHECK]

INFO_ATTACHED_FILE = "その他添付ファイルあり"
INFO_SET_BUNNY = "次回のウサギをセットしました"
INFO_BUNNY_NOW = "うさぎが来ている頃です"
INFO_NEXT_BUNNY = "次のウサギは{}ごろに来ます"

CAUTION_COMMAND_ERROR = "コマンドまちがってない?"


CHANNEL = "簡易ピン留め"  # Botの投稿先チャネル名
COMMAND_FB_TIME = 2  # unit:second
ACTIVE_COLOR = discord.Colour.dark_gold()  # Bot投稿のアクティブカラー
INACTIVE_COLOR = discord.Colour.dark_grey()  # Bot投稿のインアクティブカラー
INACTIVE_MARKUP_SYMBOLS = "||"  # Bot投稿のインアクティブ時の文字装飾

# 自動削除関係の時間設定
CLEAN_ACTIVE = True  # 自動削除を行うか否か
ZONE = ZoneInfo("Asia/Tokyo")
CLEAN_TIME = time(hour=4, minute=0, second=0, tzinfo=ZONE)
CLEAN_DAY = 1  # 0:月曜日、1:火曜日

# うさぎさんタイマー用
BUNNY_TIMER_ACTIVE = True  # 自動削除を行うか否か
# NEXT_BUNNY = time(hour=4, minute=0, second=0, tzinfo=ZONE)  # 次回ウサギが来る時間変数

#########################################
# System 環境変数の設定

# Discord.py パラメータ.
BOT_PREFIX = "!"

ERROR_MESSAGE = "function {} failed"
MESSAGE_LINK = "https://discord.com/channels/{}/{}/{}"

# Global 変数の定義
guild_channel_map = {}
#########################################
