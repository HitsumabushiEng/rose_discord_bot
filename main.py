#########################################
# TODO LIST
#
#   ・Bot書き込み用Ch名を変更できるようにする?
#   ・クラス化して整理したい。
#   ・うさぎの来る時間を調べる
#   ・imgのリンクが貼られたときの動作を修正する。
#   ・うさぎさんタスクのSeqを辞書化
#   ・sqlの要素名を辞書化
#
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
#   ・一定時間が経過したPOSTは自動で削除する。（毎週火曜朝4時）
#   ・Bot書き込み用Chを作るようマニュアルに書く
#   ・## for TEST ##をクリーンする

import os
from typing import Union
import asyncio

##
import discord
from discord.ext import commands, tasks

from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo
import re

##
import sql as sql

#########################################
DEBUG_MODE = False
# DEBUG_MODE = True

#########################################
# USER 環境変数の設定
KEYWORDS_PIN = ["📌", "📍"]
KEYWORDS_CHECK = ["✅", "☑️", "✔️"]
EMOJI_CHECK = [discord.partial_emoji.PartialEmoji.from_str(s) for s in KEYWORDS_CHECK]

INFO_ATTACHED_FILE = "その他添付ファイルあり"
INFO_SET_BUNNY = "次回のウサギをセットしました"
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
client = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


# 起動時に動作する処理
@client.event
async def on_ready():
    # 参加している各ギルドの書き込み対象chを取得、保持
    guilds = client.guilds

    if guilds is not None:
        for g in guilds:
            register_guild_ch(g)

    clean.start()  # 定期Loopの開始

    print("Test Bot logged in")


# クライアントに追加 / 削除時に反応
@client.event
async def on_guild_join(guild: discord.guild):
    register_guild_ch(guild)


@client.event
async def on_guild_remove(guild: discord.guild):
    await clear_guild_all_post(guild.id)
    erase_guild_ch(guild.id)


# メッセージ受信時に動作する処理
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
    ## ここから完了チェック
    r = sql.select_record_by_cue_message(payload.message_id, payload.guild_id)
    if r is not None:
        cue = await get_message_by_record(r, isPost=False)
        if cue is not None:
            if (payload.emoji in EMOJI_CHECK) and (payload.user_id == cue.author.id):
                await delete_post_by_record(r=r, POST=True, DB=True)
                return

    ## ここから黒塗りチェック
    elif (
        payload.channel_id == guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await get_message_by_payload(payload)
        if message.author == client.user and isFirstReactionAdd(message):
            r = sql.select_record_by_post_message(
                payload.message_id, g_id=payload.guild_id
            )
            if r is not None:
                cue = await get_message_by_record(r=r, isPost=False)
                message = await get_message_by_payload(payload)
                if message.author == client.user and isFirstReactionAdd(message):
                    await update_post(target=message, base=cue, isActive=False)
                    return
    return


# リアクション削除に対して反応
@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    ## ここから完了チェック
    try:
        message = await client.get_channel(payload.channel_id).fetch_message(
            payload.message_id
        )
    except:
        message = None
    if message is not None:
        if (
            (payload.emoji in EMOJI_CHECK)
            and (payload.user_id == message.author.id)
            and await isNoUserCheckReactions(message, payload.user_id)
        ):
            await check_and_activate(message)

    ## ここから黒塗りチェック
    if (
        payload.channel_id == guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await get_message_by_payload(payload)
        if message.author == client.user and isNullReaction(message):
            _r = sql.select_record_by_post_message(
                m_id=message.id, g_id=message.guild.id
            )
            if _r is not None:
                cue = await get_message_by_record(_r, isPost=False)
                await update_post(target=message, base=cue, isActive=True)


# クリアコマンド
@client.command()
async def clear(ctx: commands.Context):
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
async def clear_all(ctx: commands.Context):
    if ctx.message.content == BOT_PREFIX + "clear_all":  # コマンドだけに限定。
        await clear_guild_all_post(ctx.guild.id)
        msg = await ctx.send("--- all posts cleared ---")
        await asyncio.sleep(COMMAND_FB_TIME)
        await msg.delete()
        await ctx.message.delete()
    else:
        pass


# ウサギさんタイマーコマンド
@client.command()
async def usagi(ctx: commands.Context):
    if "stop" in ctx.message.content:
        await bunny_message_manage(ctx, datetime.now(), "suspend")
        usagi.cancel()

    else:
        t_str = re.search(
            r"([0-2 ０-２]){0,1}[0-9 ０-９]{1}[:：][0-5 ０-５]{0,1}[0-9 ０-９]{1}",
            ctx.message.content,
        )
        if t_str is not None:
            t_list = re.split("[:：]", t_str.group())
            t_delta = timedelta(hours=float(t_list[0]), minutes=float(t_list[1]))
            dt_next = datetime.now(tz=ZONE) + t_delta

            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=ZONE)

            usagi.change_interval(time=next)

            await post_bunny(ctx.guild.id, dt_next, seq="interval")

            try:
                usagi.start(ctx, "on_bunny")
            except:
                usagi.restart(ctx, "on_bunny")

        else:
            msg = await ctx.send(CAUTION_COMMAND_ERROR)
            await asyncio.sleep(COMMAND_FB_TIME)
            await msg.delete()

    await ctx.message.delete()

    return


#########################################
# 定期実行ルーチン
#########################################


# 自動消去ルーチン
@tasks.loop(time=CLEAN_TIME, reconnect=True)
async def clean():
    now = datetime.now(tz=ZONE)

    if now.weekday() % 7 == CLEAN_DAY and CLEAN_ACTIVE:  # 決まった曜日のみ実行
        print("定期動作作動")
        records = sql.select_records_before_yesterday()
        for r in records:
            message = await get_message_by_record(r, isPost=True)
            if (message is not None) and (
                not isNullReaction(message)
            ):  # Reactionが0じゃなかったら
                await delete_post_by_record(r, POST=True, DB=True)
                print("削除 : ", r)
    else:
        pass


# @tasks.loop(seconds=10, reconnect=True, count=3)
@tasks.loop(hours=30, reconnect=True, count=5)
async def usagi(ctx: commands.Context, seq: str):
    match seq:
        case "on_bunny":
            dt_next = datetime.now(tz=ZONE) + timedelta(minutes=10)
            # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=1)
            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=ZONE)

            await bunny_message_manage(ctx, dt_next, seq)

            usagi.change_interval(time=next)
            usagi.restart(ctx, "interval")

        case "interval":
            dt_next = datetime.now(tz=ZONE) + timedelta(hours=1, minutes=30)
            # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=2)
            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=ZONE)

            await bunny_message_manage(ctx, dt_next, seq)

            usagi.change_interval(time=next)
            usagi.restart(ctx, "on_bunny")

        case _:
            usagi.cancel()
            print(ERROR_MESSAGE.format("うさぎタイマー"))


async def bunny_message_manage(ctx: commands.Context, dt_next: datetime, seq: str):
    rs = sql.select_records_by_cue_message(
        m_id=sql.DUMMY_CUE_ID_FOR_BUNNY, g_id=ctx.guild.id
    )
    for r in rs:
        await delete_post_by_record(r, POST=True, DB=True)

    now = datetime.now(tz=ZONE)
    if 7 <= now.hour and now.hour <= 23:
        await post_bunny(ctx.guild.id, dt_next, seq)
    else:
        await post_bunny(ctx.guild.id, dt_next, "suspend")


#########################################
# Functions
#########################################


def register_guild_ch(_g: discord.Guild):
    for c in _g.channels:
        if c.name == CHANNEL:
            ## guild id -> channel を紐づけ
            global guild_channel_map
            guild_channel_map[_g.id] = c.id


def erase_guild_ch(_gid: discord.Guild.id):
    del guild_channel_map[_gid]


# メッセージが投稿・編集された時の処理
async def check_and_activate(_cue: discord.Message):
    # チェックのリアクションがついている場合、何もしない。
    if not await isNoUserCheckReactions(_cue, _cue.author.id):
        return

    # 投稿済みレコードの検索
    _record = sql.select_record_by_cue_message(_cue.id, _cue.guild.id)

    if _record is None:  # DBに書き込み元メッセージの情報がない場合
        if any((s in _cue.content) for s in KEYWORDS_PIN):
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

        if any((s in _cue.content) for s in KEYWORDS_PIN):
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
async def get_message_by_payload(
    payload: Union[
        discord.RawMessageUpdateEvent,
        discord.RawReactionActionEvent,
    ]
) -> discord.Message:
    try:
        message = (
            await client.get_guild(payload.guild_id)
            .get_channel(payload.channel_id)
            .fetch_message(payload.message_id)
        )
    except:
        message = None
    return message


# レコードからメッセージを取得
async def get_message_by_record(r: sql.record, isPost: bool = True) -> discord.Message:
    g_id = r.row["guild"]

    if isPost:
        ch_id = guild_channel_map[g_id]
        m_id = r.row["post_message_ID"]
    else:
        ch_id = r.row["cue_channel_ID"]
        m_id = r.row["cue_message_ID"]

    try:
        message = await client.get_guild(g_id).get_channel(ch_id).fetch_message(m_id)
    except:
        message = None

    return message


# ポストの新規投稿
async def new_post(_cue: discord.Message):
    _embeds = []
    _embeds = await gen_embed_from_message(_cue, isActive=True)
    try:
        msg = await client.get_channel(guild_channel_map[_cue.guild.id]).send(
            embeds=_embeds
        )
        sql.insert_record(cue=_cue, post=msg)
    except:
        print(ERROR_MESSAGE.format("new_post()"))


# InactiveになったポストのActivate
async def update_post(
    target: discord.Message, base: discord.Message, isActive: bool = True
):
    _es = []

    es = await gen_embed_from_message(base, isActive=isActive)
    _es.extend(es)
    try:
        await target.edit(embeds=_es)
    except:
        print(ERROR_MESSAGE.format("update_post()"))


async def gen_embed_from_message(
    message: discord.Message, isActive: bool
) -> [discord.Embed]:
    _es = []
    _e = discord.Embed()
    _g = await client.fetch_guild(message.guild.id)
    _m = await _g.fetch_member(message.author.id)
    _n = _m.display_name
    _l = MESSAGE_LINK.format(message.guild.id, message.channel.id, message.id)
    _l = INACTIVE_MARKUP_SYMBOLS + _l + INACTIVE_MARKUP_SYMBOLS

    _c = message.content
    for s in KEYWORDS_PIN:
        _c = _c.replace(s, "")

    if isActive:
        _e.color = ACTIVE_COLOR
    else:
        _e.color = INACTIVE_COLOR
        if _c:  # 空文字の場合は|| || で囲わない。
            _c = INACTIVE_MARKUP_SYMBOLS + _c + INACTIVE_MARKUP_SYMBOLS

    _e.set_author(name=_n, icon_url=_m.display_avatar.url)
    _e.add_field(name=_l, value=_c)

    _es.append(_e)
    _as = message.attachments

    if isActive:
        isFirst = True
        for a in _as:
            if "image" in a.content_type:
                _e = discord.Embed()
                _e.set_image(url=a.url)
                _es.append(_e)
            elif isFirst:
                _e = discord.Embed(description=INFO_ATTACHED_FILE, url=a.url)
                _es.append(_e)
                isFirst = False
    else:
        pass

    return _es


# Reactionチェック
def isNullReaction(message) -> bool:
    return not bool(message.reactions)


def isFirstReactionAdd(message) -> bool:
    return len(message.reactions) == 1 and message.reactions[0].count == 1


async def isNoUserCheckReactions(
    message: discord.Message, user: discord.User.id
) -> bool:
    for r in message.reactions:
        reaction_users = [u.id async for u in r.users()]
        if any((s in r.emoji) for s in KEYWORDS_CHECK):
            if user in reaction_users:
                return False
    return True


########### for うさぎさん
async def post_bunny(g_id: discord.Guild.id, dt_next: datetime, seq: str):
    match seq:
        case "interval":
            msg = await client.get_channel(guild_channel_map[g_id]).send(
                "次のウサギは" + dt_next.strftime("%H時%M分") + "ごろに来ます"
            )
        case "on_bunny":
            msg = await client.get_channel(guild_channel_map[g_id]).send("うさぎが来ている頃です")

        case "suspend":
            msg = None
        case _:
            msg = None

    if msg is not None:
        sql.insert_record(cue=None, post=msg)


########### Clear


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
    if POST:
        message = await get_message_by_record(r, isPost=True)
        if message is not None:
            await message.delete()
    if DB:
        m_id = r.row["post_message_ID"]
        g_id = r.row["guild"]
        sql.delete_record_by_post_message(m_id, g_id)


#########################################
# Client起動
#########################################

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
