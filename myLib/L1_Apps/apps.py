from typing import Union, Optional

##
import discord
from discord.ext import commands

from datetime import datetime

##
from myLib.L0_Core.historyCtrl import record, HistoryCtrl
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields
from myLib.L0_Core.botCtrl import BotCtrl

from myLib.L2_SystemIO.sql import SQL, bunnySQL

import myLib.L1_Apps.setting as g


#########################################
# Apps
#########################################
class AutoPin:
    def __init__(self, sqlIO: HistoryCtrl, botIO: BotCtrl) -> None:
        self.sqlIO = sqlIO
        self.botIO = botIO

    def __del__(self) -> None:
        pass

    async def pinToChannel(self, cue: discord.Message):
        gID = cue.guild.id
        chID = g.guild_channel_map[gID]
        embeds = await self.gen_embed_from_message(cue, isActive=True)

        try:
            msg = await self.botIO.sendEmbeds(gID=gID, chID=chID, embeds=embeds)
            self.sqlIO.setHistory(post=msg, cue=cue)
        except:
            print(g.ERROR_MESSAGE.format(self.pinToChannel.__name__))

    async def unpin(self, record: record):
        gID = record.guildID
        msgID = record.postID
        chID = g.guild_channel_map[gID]

        await self.botIO.deleteMessage(gID=gID, chID=chID, msgID=msgID)

        conditions = []
        conditions.append(SQLCondition(SQLFields.POST_ID, msgID))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, gID))
        self.sqlIO.deleteHistory(conditions=conditions)

    async def seal(self, target: discord.Message, base: discord.Message, isSeal: bool):
        _es = []
        es = await self.gen_embed_from_message(base, isActive=(not isSeal))
        _es.extend(es)
        try:
            await self.botIO.edit(target=target, embeds=_es)
        except:
            print(g.ERROR_MESSAGE.format(self.seal.__name__))

    async def gen_embed_from_message(
        self, message: discord.Message, isActive: bool
    ) -> [discord.Embed]:
        _es = []
        _e = discord.Embed()
        _g = await self.botIO.client.fetch_guild(message.guild.id)
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

    async def check_and_activate(self, _cue: discord.Message):
        # チェックのリアクションがついている場合、何もしない。
        if not await isNoUserCheckReactions(_cue, _cue.author.id):
            return

        # 投稿済みレコードの検索
        conditions = []
        conditions.append(SQLCondition(SQLFields.CUE_ID, _cue.id))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, _cue.guild.id))
        _record = self.sqlIO.getHistory(conditions=conditions)

        if _record is None:  # DBに書き込み元メッセージの情報がない場合
            if any((s in _cue.content) for s in g.KEYWORDS_PIN):
                await self.pinToChannel(_cue)
            else:
                pass

        else:  # DBに書き込み元メッセージの情報がある場合
            c_id = g.guild_channel_map[_record.guildID]
            m_id = _record.postID

            try:
                post = await self.botIO.client.get_channel(c_id).fetch_message(m_id)
            except:  # Bot停止中にPostが削除されており、404 Not found.
                post = None

            if any((s in _cue.content) for s in g.KEYWORDS_PIN):
                match post:
                    case None:
                        await self.pinToChannel(_cue)
                    case case if isNullReaction(case):
                        await self.seal(target=post, base=_cue, isSeal=False)
                    case _:
                        await self.seal(target=post, base=_cue, isSeal=True)

            else:  # キーワードが消えてたら、ポストを消し、レコードも消す。
                await self.unpin(_record)

        return


class BunnyTimer:
    def __init__(self, sqlIO: HistoryCtrl, botIO: BotCtrl) -> None:
        self.sqlIO = sqlIO
        self.botIO = botIO

    def __del__(self) -> None:
        pass

    async def set_bunny():
        pass


################################################
# ここから下を削除する
################################################

#########################################
# Receive client from main function.
#########################################
client: commands.Bot


def setClient(_client: commands.Bot):
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


# イベントペイロードからメッセージを取得
async def get_message_by_payload(
    payload: Union[
        discord.RawMessageUpdateEvent,
        discord.RawReactionActionEvent,
    ],
) -> Optional[discord.Message]:
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
async def get_message_by_record(
    r: record, isPost: bool = True
) -> Optional[discord.Message]:
    g_id = r.guildID

    if isPost:
        ch_id = g.guild_channel_map[g_id]
        m_id = r.postID
    else:
        ch_id = r.cueChID
        m_id = r.cueID

    try:
        message = await client.get_guild(g_id).get_channel(ch_id).fetch_message(m_id)
    except:
        message = None

    return message


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
                g.INFO_NEXT_BUNNY.format(dt_next.strftime("%H時%M分"))
            )
        case "on_bunny":
            msg = await client.get_channel(g.guild_channel_map[g_id]).send(
                g.INFO_BUNNY_NOW
            )

        case "suspend":
            msg = None
        case _:
            msg = None

    if msg is not None:
        bunnySQL.insert_record(post=msg, cue=None)


########### Clear


# Clear all posts
async def clear_guild_all_post(g_id):
    records = SQL.select_guild_all_records(g_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


# Clear own posts
async def clear_user_guild_post(g_id, u_id):
    records = SQL.select_user_guild_records(g_id, u_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)


async def delete_post_by_record(r: record, POST=False, DB=False):
    if POST:
        message = await get_message_by_record(r, isPost=True)
        if message is not None:
            await message.delete()
    if DB:
        SQL.delete_record_by_post_message(m_id=r.postID, g_id=r.guildID)
