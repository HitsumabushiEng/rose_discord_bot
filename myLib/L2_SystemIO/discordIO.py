import asyncio
from typing import Union, Optional
from enum import Enum, auto

##
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import re


##
from myLib.L0_Core.messageIF import MessageIF
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields, record

import myLib.L1_Apps.apps as apps
import myLib.L1_Apps.setting as g


class BotMixin(MessageIF):
    client: commands.Bot

    def __init__(self, client: commands.Bot) -> None:
        self.client = client
        pass

    def __del__(self) -> None:
        pass

    async def sendMessage(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        content: Union[str, discord.Embed, list[discord.Embed]],
    ) -> discord.Message:
        match type(content):
            case x if x is str:
                return (
                    await self.client.get_guild(gID)
                    .get_channel(chID)
                    .send(content=content)
                )
            case x if x is discord.Embed:
                return (
                    await self.client.get_guild(gID)
                    .get_channel(chID)
                    .send(embed=content)
                )
            case x if x is list:
                return (
                    await self.client.get_guild(gID)
                    .get_channel(chID)
                    .send(embeds=content)
                )
            case _:
                return (
                    await self.client.get_guild(gID)
                    .get_channel(chID)
                    .send(content=content)
                )

    @staticmethod
    async def editMessage(target: discord.Message, embeds: [discord.Embed]):
        await target.edit(embeds=embeds)

    @staticmethod
    async def deleteMessage(msg: discord.Message):
        if msg is not None:
            await msg.delete()

    async def getMessage_ByRecord(
        self, r: record, isPost: bool = True
    ) -> Optional[discord.Message]:
        g_id = r.guildID

        if isPost:
            ch_id = g.guild_channel_map[g_id]
            m_id = r.postID
        else:
            ch_id = r.cueChID
            m_id = r.cueID

        try:
            _msg = (
                await self.client.get_guild(g_id).get_channel(ch_id).fetch_message(m_id)
            )
        except:
            _msg = None

        return _msg

    async def getMessage(
        self,
        g_id: discord.Guild.id,
        ch_id: discord.TextChannel.id,
        m_id: discord.Member.id,
    ) -> Optional[discord.Message]:
        try:
            _msg = (
                await self.client.get_guild(g_id).get_channel(ch_id).fetch_message(m_id)
            )
        except:
            _msg = None
        return _msg


#########################################
# Cog super class
#########################################
class DiscordEventHandler(commands.Cog):
    def __init__(self, bot: commands.Bot, app: apps.myApp):
        self.client = bot
        self.app = app


#########################################
# Cog class
#########################################
class AdminEventHandler(DiscordEventHandler):
    def __init__(self, bot: commands.Bot, app: apps.AdminApp):
        self.client = bot
        self.app = app

    # 起動時に動作する処理
    @commands.Cog.listener()
    async def on_ready(self):
        self.app.register_all_guilds(self.client.guilds)
        print("Test Bot logged in")

    # ギルドに追加 / 削除時に反応
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.app.register_guild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.app.clearGuildAllMessage_History(g_id=guild.id)
        self.app.deregister_guild(guild.id)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear_all(self, ctx: commands.Context):
        if ctx.message.content == g.BOT_PREFIX + "clear_all":  # コマンドだけに限定。
            await self.app.clearGuildAllMessage_History(ctx.guild.id)
            msg = await ctx.send("--- all posts cleared ---")
            await asyncio.sleep(g.COMMAND_FB_TIME)
            await ctx.message.delete()
            await msg.delete()
        else:
            pass

    # BOTメッセージが削除された場合に反応
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        conditions = []
        conditions.append(SQLCondition(SQLFields.POST_ID, payload.message_id))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, payload.guild_id))
        _record = self.app._sqlIO.getHistory(conditions=conditions)

        if _record is not None:
            match payload.message_id:
                case _record.postID:  # 削除メッセージがPOSTの場合の処理
                    self.app.deleteHistory_ByRecord(record=_record)
                case _:
                    pass


class AutoPinEventHandler(DiscordEventHandler):
    def __init__(self, bot: commands.Bot, app: apps.AutoPinApp):
        self.client = bot
        self.app = app

    # 起動時に動作する処理
    @commands.Cog.listener()
    async def on_ready(self):
        self.clean.start()  # 定期Loopの開始
        return

    # メッセージ受信時に動作する処理
    @commands.Cog.listener("on_message")
    async def message_listener(self, message: discord.Message):
        await self._message_event_handler(message)
        return

    # メッセージ編集時に動作する処理
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        message = await self.app._botIO.getMessage(
            g_id=payload.guild_id, ch_id=payload.channel_id, m_id=payload.message_id
        )
        await self._message_event_handler(message)
        return

    # メッセージが削除された場合に反応
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        # POSTはAdmin クラスで処理。
        # CUEに対応
        conditions = []
        conditions.append(SQLCondition(SQLFields.CUE_ID, payload.message_id))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, payload.guild_id))
        _record = self.app._sqlIO.getHistory(conditions=conditions)

        if _record is not None:  # UNPIN後はレコードも消されているためNone
            match payload.message_id:
                case _record.cueID:  # 削除メッセージがCUEの場合の処理
                    await self.app.unpin_ByRecord(record=_record)
                case _:
                    pass

    # リアクション追加に対して反応
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        #
        # See decision table and flow chart bellow
        # Design\AutoPin_Decision_table.md
        #

        conditions = []
        conditions.append(SQLCondition(SQLFields.GUILD_ID, payload.guild_id))
        conditions.append(SQLCondition(SQLFields.CUE_ID, payload.message_id))
        conditions.append(SQLCondition(SQLFields.POST_ID, payload.message_id))
        record = self.app._sqlIO.getHistory(conditions=conditions)

        match record:
            case None:
                return
            case x if x.postID == payload.message_id:
                post = await self.app._botIO.getMessage_ByRecord(r=record)
                if (
                    self._isFirstReactionAdd(post)
                    and record.appName == self.app._sqlIO.appName
                ):
                    cue = await self.app._botIO.getMessage_ByRecord(
                        r=record, isPost=False
                    )
                    await self.app.seal(target=post, base=cue)
                    return
                else:
                    return
            case x if x.cueID == payload.message_id:
                cue = await self.app._botIO.getMessage_ByRecord(r=record, isPost=False)
                if cue is not None:
                    if (payload.emoji in g.EMOJI_CHECK) and (
                        payload.user_id == cue.author.id
                    ):
                        await self.app.unpin_ByRecord(record=record)
                        return
                    else:
                        return
                else:
                    return
            case _:
                return

    # リアクション削除に対して反応
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._reaction_remove_event_handler(payload=payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(
        self, payload: discord.RawReactionClearEmojiEvent
    ):
        await self._reaction_remove_event_handler(payload=payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        await self._reaction_remove_event_handler(payload=payload)

    # クリアコマンド
    @commands.command()
    async def clear(self, ctx: commands.Context):
        if ctx.message.content == g.BOT_PREFIX + "clear":  # コマンドだけに限定。
            await self.app.clear_user_guild_post(ctx.guild.id, ctx.author.id)
            msg = await ctx.send("--- your posts cleared ---")
            await asyncio.sleep(g.COMMAND_FB_TIME)
            await msg.delete()
            await ctx.message.delete()
        else:
            pass

    #########################################
    # 定期実行ルーチン
    #########################################
    # 自動消去ルーチン
    @tasks.loop(time=g.CLEAN_TIME, reconnect=True)
    async def clean(self):
        now = datetime.now(tz=g.ZONE)

        if now.weekday() % 7 == g.CLEAN_DAY and g.CLEAN_ACTIVE:  # 決まった曜日のみ実行
            print("定期動作作動")

            conditions = []
            conditions.append(SQLCondition(field=SQLFields.CREATED_AT, condition=None))
            records = self.app._sqlIO.getHistory(conditions=conditions)

            print(records)

            for r in records:
                msg = await self.app._botIO.getMessage_ByRecord(r, isPost=True)

                if msg is None:
                    self.app.deleteHistory_ByRecord(record=r)
                elif not self._isNullReaction(msg):
                    await self.app.unpin(record=r, msg=msg)
                    print("削除 : ", r)
        else:
            pass

    #########################################
    # Local methods
    #########################################
    async def _message_event_handler(self, _cue: discord.Message):
        #
        # See decision table and flow chart bellow
        # Design\AutoPin_Decision_table.md
        #

        if _cue.author.bot:
            return

        conditions = []
        conditions.append(SQLCondition(SQLFields.CUE_ID, _cue.id))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, _cue.guild.id))
        _record = self.app._sqlIO.getHistory(conditions=conditions)

        if _record is not None:
            post = await self.app._botIO.getMessage_ByRecord(_record)

        if not (any((s in _cue.content) for s in g.KEYWORDS_PIN)):
            if _record is not None:  # UNPIN
                await self.app.unpin(_record, post)
                return
            else:
                return

        if await self._isUserCheckReactions(_cue):
            if _record is not None:  # UNPIN
                await self.app.unpin(_record, post)
                return
            else:
                return

        if _record is not None:
            if self._isNullReaction(post):  # UNSEAL
                await self.app.unseal(target=post, base=_cue)
                return
            else:  # SEAL
                await self.app.seal(target=post, base=_cue)
                return

        await self.app.pinToChannel(_cue)  # pin to Channel
        return

    async def _reaction_remove_event_handler(
        self,
        payload: Union[
            discord.RawReactionActionEvent,
            discord.RawReactionClearEmojiEvent,
            discord.RawReactionClearEvent,
        ],
    ):
        #
        # See decision table and flow chart bellow
        # Design\AutoPin_Decision_table.md
        #
        conditions = []
        conditions.append(SQLCondition(SQLFields.GUILD_ID, payload.guild_id))
        conditions.append(SQLCondition(SQLFields.POST_ID, payload.message_id))
        conditions.append(SQLCondition(SQLFields.CUE_ID, payload.message_id))
        record = self.app._sqlIO.getHistory(conditions=conditions)

        match record:
            case None:  # ピンされていないメッセージのリアクションが削除された->pinToChannel判定
                match type(payload):
                    case discord.RawReactionActionEvent | discord.RawReactionClearEmojiEvent:
                        if not (payload.emoji in g.EMOJI_CHECK):  # pin to channel
                            return
                    case _:  # RawReactionClearEvent
                        pass

                cue = await self.app._botIO.getMessage(
                    g_id=payload.guild_id,
                    ch_id=payload.channel_id,
                    m_id=payload.message_id,
                )
                if not await self._isUserCheckReactions(cue):
                    if any((s in cue.content) for s in g.KEYWORDS_PIN):
                        await self.app.pinToChannel(cue=cue)
                        return
                    else:
                        return
                else:
                    return
            case x if x.postID == payload.message_id:  # Postのリアクションが削除された->unseal判定
                post = await self.app._botIO.getMessage_ByRecord(record)
                if self._isNullReaction(post):
                    cue = await self.app._botIO.getMessage_ByRecord(
                        record, isPost=False
                    )
                    await self.app.unseal(target=post, base=cue)
                    return
                else:
                    return
            case x if x.cueID == payload.message_id:
                return
            case _:
                return

    @staticmethod
    async def _isUserCheckReactions(message: discord.Message) -> bool:
        _user = message.author.id
        for r in message.reactions:
            reaction_users = [u.id async for u in r.users()]
            if any((s in r.emoji) for s in g.KEYWORDS_CHECK):
                if _user in reaction_users:
                    return True
        return False

    # Reactionチェック
    @staticmethod
    def _isNullReaction(message) -> bool:
        return not bool(message.reactions)

    @staticmethod
    def _isFirstReactionAdd(message) -> bool:
        return len(message.reactions) == 1 and message.reactions[0].count == 1

    ###############################################
    ##############ここからやる######################
    ###############################################


class BunnyTimerEventHandler(DiscordEventHandler):
    def __init__(self, bot: commands.Bot, app: apps.BunnyTimerApp):
        self.client = bot
        self.app = app

    # ウサギさんタイマーコマンド
    @commands.command()
    async def usagi(self, ctx: commands.Context):
        if "stop" in ctx.message.content:
            await self.bunny_message_manage(ctx, datetime.now(), "suspend")
            self.usagi_loop.cancel()

        else:
            t_str = re.search(
                r"([0-2 ０-２]){0,1}[0-9 ０-９]{1}[:：][0-5 ０-５]{0,1}[0-9 ０-９]{1}",
                ctx.message.content,
            )
            if t_str is not None:
                t_list = re.split("[:：]", t_str.group())
                t_delta = timedelta(hours=float(t_list[0]), minutes=float(t_list[1]))
                dt_next = datetime.now(tz=g.ZONE) + t_delta

                next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

                self.usagi_loop.change_interval(time=next)

                await self.app.post_bunny(ctx.guild.id, dt_next, seq="interval")

                try:
                    self.usagi_loop.start(ctx, "on_bunny")
                except:
                    self.usagi_loop.restart(ctx, "on_bunny")

            else:
                msg = await ctx.send(g.CAUTION_COMMAND_ERROR)
                await asyncio.sleep(g.COMMAND_FB_TIME)
                await msg.delete()

        await ctx.message.delete()

        return

    #########################################
    # 定期実行ルーチン
    #########################################

    # @tasks.loop(seconds=10, reconnect=True, count=3)
    @tasks.loop(hours=30, reconnect=True, count=5)
    async def usagi_loop(self, ctx: commands.Context, seq: str):
        match seq:
            case "on_bunny":
                dt_next = datetime.now(tz=g.ZONE) + timedelta(minutes=10)
                # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=1)
                next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

                await self.bunny_message_manage(ctx, dt_next, seq)

                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, "interval")

            case "interval":
                dt_next = datetime.now(tz=g.ZONE) + timedelta(hours=1, minutes=30)
                # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=2)
                next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

                await self.bunny_message_manage(ctx, dt_next, seq)

                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, "on_bunny")

            case _:
                self.usagi_loop.cancel()
                print(g.ERROR_MESSAGE.format("うさぎタイマー"))

    async def bunny_message_manage(
        self, ctx: commands.Context, dt_next: datetime, seq: str
    ):
        conditions = []
        conditions.append(SQLCondition(SQLFields.GUILD_ID, ctx.guild.id))
        conditions.append(SQLCondition(SQLFields.APP_NAME, self.app._sqlIO.appName))

        rs = self.app._sqlIO.getHistory(conditions=conditions)

        for r in rs:
            await self.app._deleteMessage_History_ByRecord(record=r)

        now = datetime.now(tz=g.ZONE)
        if 7 <= now.hour and now.hour <= 23:
            await self.app.post_bunny(ctx.guild.id, dt_next, seq)
        else:
            await self.app.post_bunny(ctx.guild.id, dt_next, seq="suspend")
