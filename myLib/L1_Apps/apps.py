from typing import Sequence, Optional
from datetime import datetime, timedelta
from enum import Enum, auto
import re

##
import discord

##
from myLib.L0_Core.historyIF import record, HistoryIF
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields
from myLib.L0_Core.messageIF import MessageIF

import myLib.L1_Apps.setting as g


#########################################
# Apps
#########################################
class myApp:
    def __init__(self, sqlIO: HistoryIF, botIO: MessageIF) -> None:
        self._sqlIO = sqlIO
        self._botIO = botIO

    def __del__(self) -> None:
        pass

    async def deleteMessage_History_ByRecord(self, record: record):
        msg = await self._botIO.getMessage_ByRecord(record, isPost=True)
        if msg is not None:
            await self._botIO.deleteMessage(msg=msg)
        self.deleteHistory_ByRecord(record=record)

    def deleteHistory_ByRecord(self, record: record):
        return self._sqlIO.deleteHistory_ByRecord(record=record)

    async def message_deleted(
        self, payload: discord.RawMessageDeleteEvent, record: record
    ):
        match payload.message_id:
            case record.postID:  # 削除メッセージがPOSTの場合の処理
                self.deleteHistory_ByRecord(record=record)
            case _:
                pass


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
        records = self._sqlIO.getHistory(conditions=conditions)

        for r in records:
            msg = await self._botIO.getMessage_ByRecord(r=r, isPost=True)
            await self._botIO.deleteMessage(msg=msg)
            self.deleteHistory_ByRecord(record=r)


class AutoPinApp(myApp):
    async def pinToChannel(self, cue: discord.Message):
        gID = cue.guild.id
        chID = g.guild_channel_map[gID]
        embeds = await self._gen_embed_from_message(cue, isActive=True)

        try:
            msg = await self._botIO.sendMessage(gID=gID, chID=chID, content=embeds)
            self._sqlIO.setHistory(post=msg, cue=cue)
        except:
            print(g.ERROR_MESSAGE.format(self.pinToChannel.__name__))

    async def unpin(self, record: record, msg: discord.Message):
        await self._botIO.deleteMessage(msg=msg)
        self.deleteHistory_ByRecord(record=record)

    async def unpin_ByRecord(self, record: record):
        msg = await self._botIO.getMessage_ByRecord(record, isPost=True)
        if msg is not None:
            await self._botIO.deleteMessage(msg=msg)
        self.deleteHistory_ByRecord(record=record)

    async def seal(
        self, target: discord.Message, base: discord.Message, isSeal: bool = True
    ):
        _es = []
        es = await self._gen_embed_from_message(base, isActive=(not isSeal))
        _es.extend(es)
        try:
            await self._botIO.editMessage(target=target, embeds=_es)
        except:
            print(g.ERROR_MESSAGE.format(self.seal.__name__))

    async def unseal(self, target: discord.Message, base: discord.Message):
        await self.seal(target=target, base=base, isSeal=False)

    # Clear own posts
    async def clear_user_guild_post(self, g_id, u_id):
        conditions = []
        conditions.append(SQLCondition(field=SQLFields.GUILD_ID, condition=g_id))
        conditions.append(SQLCondition(field=SQLFields.AUTHOR, condition=u_id))
        records = self._sqlIO.getHistory(conditions=conditions)

        if records is not None:
            for r in records:
                await self.deleteMessage_History_ByRecord(record=r)

    async def message_deleted(
        self, payload: discord.RawMessageDeleteEvent, record: record
    ):
        match payload.message_id:
            case record.postID:  # 削除メッセージがPOSTの場合の処理
                self.deleteHistory_ByRecord(record=record)
            case record.cueID:  # 削除メッセージがCUEの場合の処理
                await self.unpin_ByRecord(record=record)
            case _:
                pass

    # Private methods
    async def _gen_embed_from_message(
        self, message: discord.Message, isActive: bool
    ) -> [discord.Embed]:
        _es = []
        _e = discord.Embed()
        _g = await self._botIO.client.fetch_guild(message.guild.id)
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
    class BunnySeq(Enum):
        INTERVAL = auto()
        ON_BUNNY = auto()
        SUSPEND = auto()

    guild_prevMessage_map: dict[discord.Guild.id, discord.Message] = {}

    async def set_bunny():
        pass

    async def reset_bunny():
        pass

    async def catch_bunny():
        pass

    async def end_bunny():
        pass

    async def inform_next(self, g_id: discord.Guild.id, dt_next: datetime):
        await self.post_bunny(g_id=g_id, dt_next=dt_next, seq=self.BunnySeq.INTERVAL)

    async def inform_bunny(self, g_id: discord.Guild.id, dt_next: datetime):
        await self.post_bunny(g_id=g_id, dt_next=dt_next, seq=self.BunnySeq.ON_BUNNY)

    async def inform_suspend(self, g_id: discord.Guild.id, dt_next: datetime, seq: int):
        await self.post_bunny(g_id=g_id, dt_next=dt_next, seq=self.BunnySeq.SUSPEND)

    async def delete_guild_bunny_message(self, g_id: discord.Guild.id):
        conditions = []
        conditions.append(SQLCondition(SQLFields.GUILD_ID, g_id))
        conditions.append(SQLCondition(SQLFields.APP_NAME, self._sqlIO.appName))

        rs = self._sqlIO.getHistory(conditions=conditions)
        for r in rs:
            await self.deleteMessage_History_ByRecord(record=r)

    async def init_prev_message_map(self):
        for g_id in g.guild_channel_map.keys():
            self.guild_prevMessage_map[g_id] = await self.get_prev_message(g_id=g_id)

    async def message_deleted(
        self, payload: discord.RawMessageDeleteEvent, record: record
    ):
        match payload.message_id:
            case record.postID:  # 削除メッセージがPOSTの場合の処理
                self.deregister_prev_message(g_id=record.guildID)
                self.deleteHistory_ByRecord(record=record)
            case _:
                pass

    def register_prev_message(self, g_id, msg):
        self.guild_prevMessage_map[g_id] = msg

    def deregister_prev_message(self, g_id):
        self.guild_prevMessage_map[g_id] = None

    async def get_prev_message(
        self, g_id: discord.Guild.id
    ) -> Optional[discord.Message]:
        conditions = []
        conditions.append(SQLCondition(SQLFields.GUILD_ID, g_id))
        conditions.append(SQLCondition(SQLFields.APP_NAME, self._sqlIO.appName))

        rs = self._sqlIO.getHistory(conditions=conditions)
        if len(rs) != 0:
            return await self._botIO.getMessage_ByRecord(rs[-1])
        else:
            return None

    @staticmethod
    def parse_next_time(content: discord.Message.content) -> Optional[datetime]:
        t_str = re.search(
            r"([0-9 ０-９]){0,1}[0-9 ０-９]{1}[:：][0-5 ０-５]{0,1}[0-9 ０-９]{1}",
            content,
        )
        if t_str is not None:
            t_list = re.split("[:：]", t_str.group())
            t_delta = timedelta(hours=float(t_list[0]), minutes=float(t_list[1]))
            cycle_time = timedelta(hours=1, minutes=40)

            # 最初のウサギだったら、1周期分時間を短縮しておく。
            if t_delta > cycle_time:
                t_delta = t_delta - cycle_time
            dt_next = datetime.now(tz=g.ZONE) + t_delta
            return dt_next
        else:
            return None

    async def post_bunny(
        self, g_id: discord.Guild.id, dt_next: datetime, seq: BunnySeq
    ):
        chID = g.guild_channel_map[g_id]

        diff_date = dt_next.date() - datetime.now(tz=g.ZONE).date()
        match diff_date.days:
            case 0:
                date_str = g.INFO_DATE_EXPRESSION_TODAY
            case 1:
                date_str = g.INFO_DATE_EXPRESSION_TOMORROW
            case 2:
                date_str = g.INFO_DATE_EXPRESSION_DAY_AFTER_TOMORROW
            case 3:
                date_str = g.INFO_DATE_EXPRESSION_3DAYS
            case _:
                date_str = g.INFO_DATE_EXPRESSION_UNKNOWN

        match seq:
            case self.BunnySeq.INTERVAL:
                content = g.INFO_NEXT_BUNNY.format(
                    date_str, dt_next.strftime(g.BUNNY_TIME_FORMAT)
                )

                if g_id in self.guild_prevMessage_map.keys():
                    prev = self.guild_prevMessage_map[g_id]
                else:
                    prev = None  # guildで初めてのウサギメッセージ

                try:
                    await prev.fetch()
                except:
                    prev = None

                if prev is None:
                    prev = await self._botIO.sendMessage(
                        gID=g_id, chID=chID, content=content
                    )
                    self._sqlIO.setHistory(post=prev)
                else:
                    prev = await self._botIO.editMessage(target=prev, content=content)
                self.register_prev_message(g_id=g_id, msg=prev)

            case self.BunnySeq.ON_BUNNY:
                await self.delete_guild_bunny_message(g_id=g_id)
                content = g.INFO_BUNNY_NOW

                prev = await self._botIO.sendMessage(
                    gID=g_id, chID=chID, content=content
                )
                self._sqlIO.setHistory(post=prev)
                self.register_prev_message(g_id=g_id, msg=prev)

            case self.BunnySeq.SUSPEND:
                pass
            case _:
                pass
