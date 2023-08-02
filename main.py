#########################################
# TODO LIST
#   ・一定時間が経過したPOSTは自動で削除する。（毎週月曜の夜）
#
#   ・Clear all コマンド
#   ・Bot書き込み用Chを作るようマニュアルに書く
#   ・Bot書き込み用Ch名を変更できるようにする
#   ・## for TEST ##をクリーンする
#   ・cogを使ってコマンドを移動する。
# DONE
#   ・BOTのメッセージ全削除コマンドを追加する
#   ・BOTのメッセージが削除されたときにDBから削除する
#   ・キーワードが削除されたときにPOSTを消す
#   ・元メッセージが削除された場合POSTを消す
#   ・ファイルを分割する
#   ・ホストにデプロイする


import os

##
import discord
from discord.ext import commands
import asyncio

##
import sql as sql

#########################################
# USER 環境変数の設定
# KEYWORD = "#予約"
KEYWORD = "📌"
CHANNEL = "予約まとめ"
COMMAND_FB_TIME = 3  # unit:second
# DONE_EMOJI = "\N{SMILING FACE WITH OPEN MOUTH AND TIGHTLY-CLOSED EYES}"
ACTIVE_COLOR = discord.Colour.dark_gold()
INACTIVE_COLOR = discord.Colour.dark_grey()
INACTIVE_MARKUP_SYMBOLS = "||"
#########################################
# System 環境変数の設定

# Discord.py パラメータ.
REACTION_EVENT_TYPE = {"add": "REACTION_ADD", "del": "REACTION_REMOVE"}
BOT_PREFIX = "!"

# Global 変数の定義
CH_ID: str
Guild_ChID = {}
#########################################

# DBの初期接続
sql.init()

#########################################

# Token の設定 debag
#tObj = open("token")
#TOKEN = tObj.read()
Token の設定 fly.io
TOKEN = os.getenv("TOKEN")

# Intents / Client の設定 / channel初期化
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
# client = discord.Client(intents=intents)
client = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


# 起動時に動作する処理
@client.event
async def on_ready():
    # 参加しているギルドリストを取得
    guilds = client.guilds

    if guilds is not None:
        for g in guilds:
            for c in g.channels:
                if c.name == CHANNEL:
                    ## guild id -> channel を紐づけ
                    global Guild_ChID
                    Guild_ChID[g.id] = c.id
                    break
    print("Test Bot logged in")


# メッセージ受信時に動作する処理
# @client.event
# async def on_message(message):
# これは動く
@client.listen("on_message")
async def message_listener(message):
    if message.author.bot:
        return
    else:
        await check_and_activate(message)
    return


# メッセージ編集時に動作する処理
@client.event
async def on_raw_message_edit(payload):
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
    if payload.channel_id == Guild_ChID[payload.guild_id]:
        message = await get_message_by_payload(payload)
        if message.author == client.user and isFirstReaction(
            message, payload.event_type
        ):
            await deactivate_post(message)


# リアクション削除に対して反応
@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.channel_id == Guild_ChID[payload.guild_id]:
        message = await get_message_by_payload(payload)
        if message.author == client.user and isNullReaction(message):
            await activate_post(message)


@client.command()
async def clear(ctx):
    await clear_all_post(ctx.guild.id)
    msg = await ctx.send("--- all posts cleared---")
    await asyncio.sleep(COMMAND_FB_TIME)
    await msg.delete()
    await ctx.message.delete()


#########################################
# Functions
#########################################


# メッセージが投稿・編集された時の処理
async def check_and_activate(cue: discord.Message):
    _row = sql.select_record_by_cue_message(cue.id, cue.guild.id)

    if _row is None:  # 初回登録時の判定
        # KEYWORDを発言したら動く処理
        if KEYWORD in cue.content:
            _embed = discord.Embed()
            _embed.color = ACTIVE_COLOR
            _embed.add_field(
                name=cue.author.display_name,
                value=cue.content.replace(KEYWORD, ""),
            )

            msg = await client.get_channel(Guild_ChID[cue.guild.id]).send(embed=_embed)
            sql.insert_record(cue=cue, post=msg)
        else:
            None

    else:  # 2回目以降の処理
        g_id = Guild_ChID[_row.row["guild"]]
        m_id = _row.row["post_message_ID"]
        post = await client.get_channel(g_id).fetch_message(m_id)

        if KEYWORD in cue.content:
            if isNullReaction(post):
                await activate_post(target=post, base=cue)
            else:
                await deactivate_post(target=post, base=cue)
        else:  # キーワードが消えてたら、ポストを消し、レコードも消す。
            sql.delete_record_by_post_message(post.id, post.guild.id)
            await post.delete()

    return


# リアクション時のメッセージ取得
async def get_message_by_payload(payload):
    txt_channel = client.get_channel(payload.channel_id)
    message = await txt_channel.fetch_message(payload.message_id)
    return message


# InactiveになったポストのActivate
async def activate_post(target, base=None):
    _es = []

    if base is None:
        base = target
        _es = gen_embeds(base, isActive=True)

    else:
        e = discord.Embed()
        e.color = ACTIVE_COLOR
        _name = base.author.display_name
        _value = base.content.replace(KEYWORD, "")
        e.add_field(name=_name, value=_value)
        _es.append(e)

    await target.edit(embeds=_es)


# ポストのDeactivate
async def deactivate_post(target, base=None):
    _es = []

    if base is None:
        base = target
        _es = gen_embeds(base, isActive=False)

    else:
        e = discord.Embed()
        e.color = INACTIVE_COLOR
        _name = (
            INACTIVE_MARKUP_SYMBOLS + base.author.display_name + INACTIVE_MARKUP_SYMBOLS
        )
        _value = (
            INACTIVE_MARKUP_SYMBOLS
            + base.content.replace(KEYWORD, "")
            + INACTIVE_MARKUP_SYMBOLS
        )
        e.add_field(name=_name, value=_value)
        _es.append(e)

    await target.edit(embeds=_es)


def gen_embeds(base, isActive):
    i = 0
    _es = []
    if isActive:  # generate Active post embeds
        for e in base.embeds:
            e.color = ACTIVE_COLOR
            for f in e.fields:
                _name = f.name.replace(INACTIVE_MARKUP_SYMBOLS, "")
                _value = f.value.replace(INACTIVE_MARKUP_SYMBOLS, "")
                inline = f.inline
                e.set_field_at(i, name=_name, value=_value, inline=inline)
                i += 1
            _es.append(e)
    else:  # generate Inactive post embeds
        for e in base.embeds:
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


def isFirstReaction(message, event_type):
    return (
        len(message.reactions) == 1
        and message.reactions[0].count == 1
        and event_type == REACTION_EVENT_TYPE["add"]
    )


# Clear all post
async def clear_all_post(g_id):
    records = sql.select_guild_all_records(g_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


async def delete_post_by_record(r, POST=False, DB=False):
    m_id = r.row["post_message_ID"]
    g_id = r.row["guild"]
    ch_id = Guild_ChID[g_id]

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
