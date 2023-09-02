from typing import Union
import asyncio

##
import discord
from discord.ext import commands

from datetime import datetime

##
import myLib.L2_SystemIO.sql as sql
import myLib.L1_Apps.setting as g


#########################################
# Receive client from main function.
#########################################
client: commands.bot


def setClient(_client: commands.bot):
    global client
    client = _client


#########################################
# Functions
#########################################


def register_guild_ch(_g: discord.Guild):
    for c in _g.channels:
        if c.name == g.CHANNEL:
            ## guild id -> channel を紐づけ
            g.guild_channel_map[_g.id] = c.id


def erase_guild_ch(_gid: discord.Guild.id):
    del g.guild_channel_map[_gid]


# メッセージが投稿・編集された時の処理
async def check_and_activate(_cue: discord.Message):
    # チェックのリアクションがついている場合、何もしない。
    if not await isNoUserCheckReactions(_cue, _cue.author.id):
        return

    # 投稿済みレコードの検索
    _record = sql.select_record_by_cue_message(_cue.id, _cue.guild.id)

    if _record is None:  # DBに書き込み元メッセージの情報がない場合
        if any((s in _cue.content) for s in g.KEYWORDS_PIN):
            await new_post(_cue)
        else:
            pass

    else:  # DBに書き込み元メッセージの情報がある場合
        c_id = g.guild_channel_map[_record.row["guild"]]
        m_id = _record.row["post_message_ID"]

        try:
            post = await client.get_channel(c_id).fetch_message(m_id)
        except:  # Bot停止中にPostが削除されており、404 Not found.
            post = None

        if any((s in _cue.content) for s in g.KEYWORDS_PIN):
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
    ],
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
        ch_id = g.guild_channel_map[g_id]
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
        msg = await client.get_channel(g.guild_channel_map[_cue.guild.id]).send(
            embeds=_embeds
        )
        sql.insert_record(cue=_cue, post=msg)
    except:
        print(g.ERROR_MESSAGE.format("new_post()"))


# InactiveになったポストのActivate
async def update_post(
    target: discord.Message,
    base: discord.Message,
    isActive: bool = True,
):
    _es = []

    es = await gen_embed_from_message(base, isActive=isActive)
    _es.extend(es)
    try:
        await target.edit(embeds=_es)
    except:
        print(g.ERROR_MESSAGE.format("update_post()"))


async def gen_embed_from_message(
    message: discord.Message, isActive: bool
) -> [discord.Embed]:
    _es = []
    _e = discord.Embed()
    _g = await client.fetch_guild(message.guild.id)
    _m = await _g.fetch_member(message.author.id)
    _n = _m.display_name
    _l = g.MESSAGE_LINK.format(message.guild.id, message.channel.id, message.id)
    _l = g.INACTIVE_MARKUP_SYMBOLS + _l + g.INACTIVE_MARKUP_SYMBOLS

    _c = message.content
    for s in g.KEYWORDS_PIN:
        _c = _c.replace(s, "")

    if isActive:
        _e.color = g.ACTIVE_COLOR
    else:
        _e.color = g.INACTIVE_COLOR
        if _c:  # 空文字の場合は|| || で囲わない。
            _c = g.INACTIVE_MARKUP_SYMBOLS + _c + g.INACTIVE_MARKUP_SYMBOLS

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
                _e = discord.Embed(description=g.INFO_ATTACHED_FILE, url=a.url)
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
        if any((s in r.emoji) for s in g.KEYWORDS_CHECK):
            if user in reaction_users:
                return False
    return True


########### for うさぎさん
async def post_bunny(g_id: discord.Guild.id, dt_next: datetime, seq: str):
    match seq:
        case "interval":
            msg = await client.get_channel(g.guild_channel_map[g_id]).send(
                "次のウサギは" + dt_next.strftime("%H時%M分") + "ごろに来ます"
            )
        case "on_bunny":
            msg = await client.get_channel(g.guild_channel_map[g_id]).send(
                "うさぎが来ている頃です"
            )

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
