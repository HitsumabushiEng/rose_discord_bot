import asyncio
from typing import Union

##
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta


##
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields

import myLib.L1_Apps.apps as apps
import myLib.L1_Apps.setting as g


#########################################
# Cog super class
#########################################
class DiscordEventHandler(commands.Cog):
    def __init__(self, bot: commands.Bot, app: apps.myApp):
        self.client = bot
        self.app = app

    # BOTメッセージが削除された場合に反応
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        conditions = []
        conditions.append(SQLCondition(SQLFields.POST_ID, payload.message_id))
        conditions.append(SQLCondition(SQLFields.GUILD_ID, payload.guild_id))
        _record = self.app._sqlIO.getHistory(conditions=conditions)

        if _record is not None:
            if _record.appName is self.app._sqlIO.appName:
                match payload.message_id:
                    case _record.postID:  # 削除メッセージがPOSTの場合の処理
                        self.app.deleteHistory_ByRecord(record=_record)
                    case _:
                        pass


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


#    @commands.command()
#    @commands.has_permissions(manage_messages=True)
#    async def clear_all(self, ctx: commands.Context):
#        if ctx.message.content == g.BOT_PREFIX + "clear_all":  # コマンドだけに限定。
#            self.app.deregister_prev_message(g_id=ctx.guild.id)


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


class BunnyTimerEventHandler(DiscordEventHandler):
    def __init__(self, bot: commands.Bot, app: apps.BunnyTimerApp):
        self.client = bot
        self.app = app

    # 起動時に動作する処理
    @commands.Cog.listener()
    async def on_ready(self):
        await self.app.init_prev_message_map()
        return

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        self.app.deregister_prev_message(g_id=guild.id)

    # ウサギさんタイマーコマンド
    @commands.command()
    async def usagi(self, ctx: commands.Context):
        if "stop" in ctx.message.content:
            # delete message and history
            g_id = ctx.guild.id
            await self.app.delete_guild_bunny_message(g_id=g_id)
            self.app.deregister_prev_message(g_id=g_id)
            # inform suspend
            await self.app.inform_suspend(
                g_id=g_id,
                dt_next=datetime.now(tz=g.ZONE),
                seq=self.app.BunnySeq.SUSPEND,
            )  # 現状、なにもなし
            # process cancel
            self.usagi_loop.cancel()

        else:
            # get next datetime from message
            dt_next = self.app.parse_next_time(content=ctx.message.content)

            if dt_next is not None:
                next = self.convert_datetime_to_time(dt_next)
                # activate process with next "time"
                self.usagi_loop.change_interval(time=next)
                if not bool(self.usagi_loop.next_iteration):
                    self.usagi_loop.start(ctx, self.app.BunnySeq.ON_BUNNY)
                else:
                    self.usagi_loop.restart(ctx, self.app.BunnySeq.ON_BUNNY)
                # inform
                await self.app.inform_next(g_id=ctx.guild.id, dt_next=dt_next)

            else:
                msg = await ctx.send(g.CAUTION_COMMAND_ERROR)
                await asyncio.sleep(g.COMMAND_FB_TIME)
                await msg.delete()

        await ctx.message.delete()

        return

    #########################################
    # 定期実行ルーチン
    #########################################

    @tasks.loop(hours=30, reconnect=True, count=5)
    async def usagi_loop(self, ctx: commands.Context, seq: apps.BunnyTimerApp.BunnySeq):
        match seq:
            case self.app.BunnySeq.ON_BUNNY:
                # 次のタイマー時間を計算し
                dt_next = datetime.now(tz=g.ZONE) + timedelta(minutes=10)
                next = self.convert_datetime_to_time(dt_next)
                # (いつまで)ウサギがいることを伝える。
                await self.app.inform_bunny(g_id=ctx.guild.id, dt_next=dt_next)

                # 次のタイマーをセットする
                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, self.app.BunnySeq.INTERVAL)

            case self.app.BunnySeq.INTERVAL:
                # 次にウサギが来る時間を計算して
                dt_next = datetime.now(tz=g.ZONE) + timedelta(hours=1, minutes=30)
                next = self.convert_datetime_to_time(dt_next)
                # 次にウサギが来る時間を知らせる
                await self.app.inform_next(g_id=ctx.guild.id, dt_next=dt_next)

                # 次のタイマーをセットする
                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, self.app.BunnySeq.ON_BUNNY)

            case _:
                self.usagi_loop.cancel()
                print(g.ERROR_MESSAGE.format("うさぎタイマー"))

    @staticmethod
    def convert_datetime_to_time(dt: datetime) -> time:
        return time(hour=dt.hour, minute=dt.minute, tzinfo=g.ZONE)
