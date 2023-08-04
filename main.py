#########################################
# TODO LIST
#   ・一定時間が経過したPOSTは自動で削除する。（毎週月曜の夜）
#
#   ・Bot書き込み用Chを作るようマニュアルに書く
#   ・Bot書き込み用Ch名を変更できるようにする
#   ・## for TEST ##をクリーンする
# DONE
#   ・BOTのメッセージ全削除コマンドを追加する
#   ・BOTのメッセージが削除されたときにDBから削除する
#   ・キーワードが削除されたときにPOSTを消す
#   ・元メッセージが削除された場合POSTを消す
#   ・ファイルを分割する
#   ・ホストにデプロイする
#   ・途中から参加／抜けるサーバに対応
#   ・！clearコマンドは、それ以外を含まない投稿のみとする。
#   ・！clear_allコマンドは、管理者と特定の権限（メッセージ削除）を持つ人のみ実行可能にする。
#   ・！clearコマンドは、実行者の自分のポストのみを削除
#   ・Error回避のtry except を作る。

import os

##
import discord
from discord.ext import commands
import asyncio

##
import sql as sql

#########################################
DEBUG_MODE = False
# DEBUG_MODE = True

#########################################
# USER 環境変数の設定
# KEYWORD = "#予約"
KEYWORD = "📌"
CHANNEL = "簡易ピン留め"
COMMAND_FB_TIME = 2  # unit:second
# DONE_EMOJI = "\N{SMILING FACE WITH OPEN MOUTH AND TIGHTLY-CLOSED EYES}"
ACTIVE_COLOR = discord.Colour.dark_gold()
INACTIVE_COLOR = discord.Colour.dark_grey()
INACTIVE_MARKUP_SYMBOLS = "||"
#########################################
# System 環境変数の設定

# Discord.py パラメータ.
BOT_PREFIX = "!"

ERROR_MESSAGE = "function {} failed"
MESSAGE_LINK = "https://discord.com/channels/{}/{}/{}"

# Global 変数の定義
guild_channel_map = {}
#########################################

# DBの初期接続
sql.init()

#########################################
# Token の設定
if DEBUG_MODE:  # Local Token
    tObj = open("token_dev")  # for Earnest
    #   tObj = open("token")      #for Rose
    TOKEN = tObj.read()
else:  # fly.io
    TOKEN = os.getenv("TOKEN")

#########################################

# Intents / Client の設定 / channel初期化
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
# client = discord.Client(intents=intents)
client = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


# 起動時に動作する処理
@client.event
async def on_ready():
    # 参加している各ギルドの書き込み対象chを取得、保持
    guilds = client.guilds

    if guilds is not None:
        for g in guilds:
            register_guild_ch(g)
    print("Test Bot logged in")


# クライアントに追加 / 削除時に反応
@client.event
async def on_guild_join(guild: discord.guild):
    register_guild_ch(guild)


@client.event
async def on_guild_remove(guild: discord.guild):
    await clear_guild_all_post(guild.id)


# メッセージ受信時に動作する処理
# @client.event
# async def on_message(message):
@client.listen("on_message")
async def message_listener(message: discord.Message):
    if message.author.bot:
        return
    else:
        await check_and_activate(message)
    return


# メッセージ編集時に動作する処理
@client.event
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    message = await get_message_by_payload(payload)
    if message.author.bot:
        return
    else:
        await check_and_activate(message)
    return


# メッセージが削除された場合に反応
@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    # 削除メッセージがBOTの場合の処理
    _record = sql.select_record_by_post_message(payload.message_id, payload.guild_id)
    if _record is not None:
        await delete_post_by_record(_record, POST=False, DB=True)
    else:
        pass

    # 削除メッセージがCueの場合の処理
    _record = sql.select_record_by_cue_message(payload.message_id, payload.guild_id)
    if _record is not None:
        await delete_post_by_record(_record, POST=True, DB=True)
    else:
        pass


# リアクション追加に対して反応
@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if (
        payload.channel_id == guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await get_message_by_payload(payload)
        if message.author == client.user and isFirstReactionAdd(message):
            await update_post(message, isActive=False)


# リアクション削除に対して反応
@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if (
        payload.channel_id == guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await get_message_by_payload(payload)
        if message.author == client.user and isNullReaction(message):
            await update_post(message, isActive=True)


@client.command()
async def clear(ctx):
    if ctx.message.content == BOT_PREFIX + "clear":  # コマンドだけに限定。
        await clear_user_guild_post(ctx.guild.id, ctx.author.id)
        msg = await ctx.send("--- your posts cleared ---")
        await asyncio.sleep(COMMAND_FB_TIME)
        await msg.delete()
        await ctx.message.delete()
    else:
        pass


@client.command()
@commands.has_permissions(manage_messages=True)
# @commands.is_owner()
async def clear_all(ctx):
    if ctx.message.content == BOT_PREFIX + "clear_all":  # コマンドだけに限定。
        await clear_guild_all_post(ctx.guild.id)
        msg = await ctx.send("--- all posts cleared ---")
        await asyncio.sleep(COMMAND_FB_TIME)
        await msg.delete()
        await ctx.message.delete()
    else:
        pass


#########################################
# Functions
#########################################


def register_guild_ch(_g: discord.Guild):
    for c in _g.channels:
        if c.name == CHANNEL:
            ## guild id -> channel を紐づけ
            global guild_channel_map
            guild_channel_map[_g.id] = c.id


# メッセージが投稿・編集された時の処理
async def check_and_activate(_cue: discord.Message):
    _record = sql.select_record_by_cue_message(_cue.id, _cue.guild.id)

    if _record is None:  # DBに書き込み元メッセージの情報がない場合
        if KEYWORD in _cue.content:
            await new_post(_cue)
        else:
            pass

    else:  # DBに書き込み元メッセージの情報がある場合
        c_id = guild_channel_map[_record.row["guild"]]
        m_id = _record.row["post_message_ID"]

        try:
            post = await client.get_channel(c_id).fetch_message(m_id)
        except:  # Bot停止中にPostが削除されており、404 Not found.
            post = None

        if KEYWORD in _cue.content:
            match post:
                case None:
                    await new_post(_cue)
                case case if isNullReaction(case):
                    await update_post(target=post, base=_cue, isActive=True)
                case _:
                    await update_post(target=post, base=_cue, isActive=False)

        else:  # キーワードが消えてたら、ポストを消し、レコードも消す。
            await delete_post_by_record(_record, POST=True, DB=True)

    return


# イベントペイロードからメッセージを取得
async def get_message_by_payload(payload):
    txt_channel = client.get_channel(payload.channel_id)
    message = await txt_channel.fetch_message(payload.message_id)
    return message


# ポストの新規投稿
async def new_post(_cue: discord.Message):
    _embed = gen_embed_from_message(_cue, isActive=True)
    try:
        msg = await client.get_channel(guild_channel_map[_cue.guild.id]).send(
            embed=_embed
        )
        sql.insert_record(cue=_cue, post=msg)
    except:
        print(ERROR_MESSAGE.format("new_post()"))


# InactiveになったポストのActivate
async def update_post(
    target: discord.Message, base: discord.Message = None, isActive: bool = True
):
    _es = []

    if base is None:  # リアクションの変化によるActive/Deactiveの変更
        _es = update_embeds(target, isActive=isActive)

    else:  # 新規投稿、既存メッセージの編集によるポストの追加
        e = gen_embed_from_message(base, isActive=isActive)
        _es.append(e)
    try:
        await target.edit(embeds=_es)
    except:
        print(ERROR_MESSAGE.format("update_post()"))


def gen_embed_from_message(message: discord.Message, isActive: bool) -> discord.Embed:
    _e = discord.Embed()
    _n = message.author.display_name
    _n = (
        _n
        + "   :   "
        + MESSAGE_LINK.format(message.guild.id, message.channel.id, message.id)
    )

    _v = message.content.replace(KEYWORD, "")

    if isActive:
        _e.color = ACTIVE_COLOR
    else:
        _e.color = INACTIVE_COLOR
        _n = INACTIVE_MARKUP_SYMBOLS + _n + INACTIVE_MARKUP_SYMBOLS
        _v = INACTIVE_MARKUP_SYMBOLS + _v + INACTIVE_MARKUP_SYMBOLS
    _e.add_field(name=_n, value=_v)
    return _e


def update_embeds(target: discord.Message, isActive: bool):
    _es = []
    for e in target.embeds:
        i = 0
        if isActive:  # generate Active post embeds
            e.color = ACTIVE_COLOR
            for f in e.fields:
                _name = f.name.replace(INACTIVE_MARKUP_SYMBOLS, "")
                _value = f.value.replace(INACTIVE_MARKUP_SYMBOLS, "")
                inline = f.inline
                e.set_field_at(i, name=_name, value=_value, inline=inline)
                i += 1
        else:  # generate Inactive post embeds
            e.color = INACTIVE_COLOR
            for f in e.fields:
                name = INACTIVE_MARKUP_SYMBOLS + f.name + INACTIVE_MARKUP_SYMBOLS
                value = INACTIVE_MARKUP_SYMBOLS + f.value + INACTIVE_MARKUP_SYMBOLS
                inline = f.inline
                e.set_field_at(i, name=name, value=value, inline=inline)
                i += 1
        _es.append(e)

    return _es


# Reactionチェック
def isNullReaction(message):
    return not bool(message.reactions)


def isFirstReactionAdd(message):
    return len(message.reactions) == 1 and message.reactions[0].count == 1


# Clear all posts
async def clear_guild_all_post(g_id):
    records = sql.select_guild_all_records(g_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


# Clear own posts
async def clear_user_guild_post(g_id, u_id):
    records = sql.select_user_guild_records(g_id, u_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


async def delete_post_by_record(r, POST=False, DB=False):
    m_id = r.row["post_message_ID"]
    g_id = r.row["guild"]
    ch_id = guild_channel_map[g_id]

    if POST:
        try:
            message = await client.get_channel(ch_id).fetch_message(m_id)
        except:
            message = None

        if message is not None:
            await message.delete()
    if DB:
        sql.delete_record_by_post_message(m_id, g_id)


# post_message_ID, cue_message_ID, created_at, author

#########################################
# Client起動
#########################################

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
