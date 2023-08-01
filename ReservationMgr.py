#########################################
# TODO LIST
#   ・一定時間が経過したPOSTは自動で削除する。（毎週月曜の夜）
#   ・ファイルを分割する
#   ・ホストにデプロイする
#   ・元メッセージが削除された場合
#
#   ・Clear all コ
#   ・Bot書き込み用Chを作るようマニュアルに書く
#   ・Bot書き込み用Ch名を変更できるようにする
#   ・## for TEST ##をクリーンする
#
# DONE
#   ・BOTのメッセージ全削除コマンドを追加する
#   ・BOTのメッセージが削除されたときにDBから削除する
#   ・キーワードが削除されたときにPOSTを消す


import os
import discord
from discord.ext import commands
import asyncio
import sqlite3

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
DB_NAME = "System.db"

# Discord.py パラメータ.
REACTION_EVENT_TYPE = {"add": "REACTION_ADD", "del": "REACTION_REMOVE"}
BOT_PREFIX = "!"

# Global 変数の定義
CH_ID: str
#########################################

# クエリ
CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS
        post_list(
            post_message_ID INTEGER PRIMARY KEY,
            cue_message_ID INTEGER,
            created_at TEXT NOT NULL,
            author INTEGER NOT NULL)
    """
INSERT_RECORDS = """
    INSERT INTO
    post_list (post_message_ID, cue_message_ID, created_at, author)
    VALUES (:post_message_ID, :cue_message_ID, :created_at, :author);
    """
SELECT_ALL_VALUE = "SELECT * FROM post_list;"
SELECT_VALUE_BY_CUE_MESSAGE_ID = """
    SELECT * FROM post_list
    where cue_message_ID=:ID;
"""
SELECT_VALUE_BY_POST_MESSAGE_ID = """
    SELECT * FROM post_list
    where post_message_ID=:ID;
"""
DELETE_ALL_VALUE = "DELETE FROM post_list;"
DELETE_VALUE_BY_CUE_MESSAGE_ID = """
    DELETE FROM post_list
    where cue_message_ID=:ID;
"""
DELETE_VALUE_BY_POST_MESSAGE_ID = """
    DELETE FROM post_list
    where post_message_ID=:ID;
"""
# SELECT_TYPE_OF_COLUMNS = "SELECT typeof(t1), typeof(t2),typeof(t3),typeof(t4),typeof(t5) FROM example;"


#########################################
# データクラス定義
#########################################
class record:
    row = {}

    def __init__(self):
        self.row = {}

    def __init__(self, post_message_ID, cue_message_ID, created_at, author):
        self.row = {
            "post_message_ID": post_message_ID,
            "cue_message_ID": cue_message_ID,
            "created_at": created_at,
            "author": author,
        }


# DB操作Function
def SQL_init():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE)
    conn.commit()
    cur.execute(SELECT_ALL_VALUE)
    for r in cur:
        print(*r)

    conn.close()


def SQL_insert_record(cue, post):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    _record = record(post.id, cue.id, cue.created_at, cue.author.id)
    cur.execute(INSERT_RECORDS, _record.row)
    conn.commit()
    conn.close()


def SQL_select_all_records():
    _records = []
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_ALL_VALUE)
    for row in cur:
        if row is not None:
            _records.append(record(*row))
    conn.close()
    return _records


def SQL_select_record_by_cue_message_id(id):
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_CUE_MESSAGE_ID, {"ID": id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


def SQL_select_record_by_post_message_id(id):
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_POST_MESSAGE_ID, {"ID": id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


def SQL_delete_all_records():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_ALL_VALUE)
    conn.commit()
    conn.close()


def SQL_delete_record_by_cue_message_id(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_CUE_MESSAGE_ID, {"ID": id})
    conn.commit()
    conn.close()


def SQL_delete_record_by_post_message_id(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_POST_MESSAGE_ID, {"ID": id})
    conn.commit()
    conn.close()


# DBの初期接続
SQL_init()

#########################################

# Token の設定
# tObj = open("token")
# TOKEN = tObj.read()
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
    # 書き込み対象チャンネル取得、ログイン通知
    for ch in client.get_all_channels():
        if ch.name == CHANNEL:
            global CH_ID
            CH_ID = ch.id
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
async def on_raw_message_delete(payload):
    # 削除メッセージがBOTの場合の処理
    _record = SQL_select_record_by_post_message_id(payload.message_id)
    if _record is not None:
        await delete_post_by_record(_record, POST=False, DB=True)
    else:
        pass

    # 削除メッセージがCueの場合の処理
    _record = SQL_select_record_by_cue_message_id(payload.message_id)
    if _record is not None:
        await delete_post_by_record(_record, POST=True, DB=True)
    else:
        pass


# リアクション追加に対して反応
@client.event
async def on_raw_reaction_add(payload):
    if payload.channel_id == CH_ID:
        message = await get_message_by_payload(payload)
        if message.author == client.user and isFirstReaction(
            message, payload.event_type
        ):
            await deactivate_post(message)


# リアクション削除に対して反応
@client.event
async def on_raw_reaction_remove(payload):
    if payload.channel_id == CH_ID:
        message = await get_message_by_payload(payload)
        if message.author == client.user and isNullReaction(message):
            await activate_post(message)


@client.command()
async def clear(ctx):
    await clear_all_post()
    msg = await ctx.send("--- all posts cleared---")
    await asyncio.sleep(COMMAND_FB_TIME)
    await msg.delete()
    await ctx.message.delete()


#########################################
# Functions
#########################################


# メッセージが投稿・編集された時の処理
async def check_and_activate(cue):
    _row = SQL_select_record_by_cue_message_id(cue.id)

    if _row is None:  # 初回登録時の判定
        # KEYWORDを発言したら動く処理
        if KEYWORD in cue.content:
            _embed = discord.Embed()
            _embed.color = ACTIVE_COLOR
            _embed.add_field(
                name=cue.author.display_name,
                value=cue.content.replace(KEYWORD, ""),
            )

            msg = await client.get_channel(CH_ID).send(embed=_embed)
            SQL_insert_record(cue=cue, post=msg)
        else:
            None

    else:  # 2回目以降の処理
        post = await client.get_channel(CH_ID).fetch_message(
            _row.row["post_message_ID"]
        )

        if KEYWORD in cue.content:
            if isNullReaction(post):
                await activate_post(target=post, base=cue)
            else:
                await deactivate_post(target=post, base=cue)
        else:  # キーワードが消えてたら、ポストを消し、レコードも消す。
            SQL_delete_record_by_post_message_id(post.id)
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
async def clear_all_post():
    records = SQL_select_all_records()
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


async def delete_post_by_record(r, POST=False, DB=False):
    if POST:
        message = await client.get_channel(CH_ID).fetch_message(
            r.row["post_message_ID"]
        )
        await message.delete()
    if DB:
        SQL_delete_record_by_post_message_id(r.row["post_message_ID"])


# post_message_ID, cue_message_ID, created_at, author

#########################################
# Client起動
#########################################

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
