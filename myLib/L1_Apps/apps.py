from typing import Union, Optional, Sequence

##
import discord
from discord.ext import commands

from datetime import datetime

##
from myLib.L0_Core.historyIF import record, HistoryIF
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields
from myLib.L0_Core.messageIF import MessageIF

from myLib.L2_SystemIO.sql import SQL, bunnySQL

import myLib.L1_Apps.setting as g


#########################################
# Apps
#########################################
class myApp:
    def __init__(self, sqlIO: HistoryIF, botIO: MessageIF) -> None:
        self.sqlIO = sqlIO
        self.botIO = botIO

    def __del__(self) -> None:
        pass

    async def deleteMessage_History_ByRecord(self, record: record):
        msg = await self.botIO.getMessage_ByRecord(record, isPost=True)
        if msg is not None:
            await self.botIO.deleteMessage(msg=msg)
        self.sqlIO.deleteHistory_ByRecord(record=record)

    async def __deleteHistory_ByRecord(self, record: record):
        return self.sqlIO.deleteHistory_ByRecord(record=record)


class AdminApp(myApp):
    @classmethod
    def register_all_guilds(cls, _guilds: Sequence[discord.Guild]):
        # 参加している各ギルドの書き込み対象chを取得、保持
        if _guilds is not None:
            for g in _guilds:
                cls.register_guild(g)

    @staticmethod
    def register_guild(_g: discord.Guild):
        for c in _g.channels:
            if c.name == g.CHANNEL:
                ## guild id -> channel を紐づけ
                g.guild_channel_map[_g.id] = c.id

    @staticmethod
    def deregister_guild(_gid: discord.Guild.id):
        del g.guild_channel_map[_gid]

    async def clearGuildAllMessage_History(self, g_id):
        conditions = []
        conditions.append(SQLCondition(field=SQLFields.GUILD_ID, condition=g_id))
        records = self.sqlIO.getHistory(conditions=conditions)

        for r in records:
            msg = await self.botIO.getMessage_ByRecord(r=r, isPost=True)
            await self.botIO.deleteMessage(msg=msg)
            self.sqlIO.deleteHistory_ByRecord(record=r)


class AutoPinApp(myApp):
    async def pinToChannel(self, cue: discord.Message):
        gID = cue.guild.id
        chID = g.guild_channel_map[gID]
        embeds = await self.__gen_embed_from_message(cue, isActive=True)

        try:
            msg = await self.botIO.sendMessage(gID=gID, chID=chID, content=embeds)
            self.sqlIO.setHistory(post=msg, cue=cue)
        except:
            print(g.ERROR_MESSAGE.format(self.pinToChannel.__name__))

    async def unpin(self, record: record, msg: discord.Message):
        await self.botIO.deleteMessage(msg=msg)
        self.sqlIO.deleteHistory_ByRecord(record=record)

    async def seal(
        self, target: discord.Message, base: discord.Message, isSeal: bool = True
    ):
        _es = []
        es = await self.__gen_embed_from_message(base, isActive=(not isSeal))
        _es.extend(es)
        try:
            await self.botIO.editMessage(target=target, embeds=_es)
        except:
            print(g.ERROR_MESSAGE.format(self.seal.__name__))

    async def unseal(self, target: discord.Message, base: discord.Message):
        await self.seal(target=target, base=base, isSeal=False)

    # Clear own posts
    async def clear_user_guild_post(self, g_id, u_id):
        conditions = []
        conditions.append(SQLCondition(field=SQLFields.GUILD_ID, condition=g_id))
        conditions.append(SQLCondition(field=SQLFields.AUTHOR, condition=u_id))
        records = self.sqlIO.getHistory(conditions=conditions)

        if records is not None:
            for r in records:
                self.deleteMessage_History_ByRecord(record=r)

    # Private methods
    async def __gen_embed_from_message(
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


class BunnyTimerApp(myApp):
    async def set_bunny():
        pass

    async def reset_bunny():
        pass

    async def catch_bunny():
        pass

    async def end_bunny():
        pass

    async def inform_next():
        pass

    async def inform_bunny():
        pass

    async def post_bunny(self, g_id: discord.Guild.id, dt_next: datetime, seq: str):
        chID = g.guild_channel_map[g_id]

        match seq:
            case "interval":
                content = g.INFO_NEXT_BUNNY.format(
                    dt_next.strftime(g.BUNNY_TIME_FORMAT)
                )
            case "on_bunny":
                content = g.INFO_BUNNY_NOW
            case "suspend":
                content = None
            case _:
                content = None

        if content is not None:
            msg = await self.botIO.sendMessage(gID=g_id, chID=chID, content=content)
            bunnySQL.insert_record(post=msg, cue=None)


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


########### Clear

"""
# Clear all posts
async def clear_guild_all_post(g_id):
    records = SQL.select_guild_all_records(g_id)
    for r in records:
        await delete_post_by_record(r, POST=True, DB=True)
"""

"""
async def delete_post_by_record(r: record, POST=False, DB=False):
    if POST:
        message = await get_message_by_record(r, isPost=True)
        if message is not None:
            await message.delete()
    if DB:
        SQL.delete_record_by_post_message(m_id=r.postID, g_id=r.guildID)
"""
