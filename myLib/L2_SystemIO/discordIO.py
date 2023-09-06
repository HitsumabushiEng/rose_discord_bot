import asyncio
from typing import Union, Optional

##
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import re

from discord.guild import Guild

##
from myLib.L0_Core.messageIF import MessageIF
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields, record

from myLib.L2_SystemIO.sql import SQL, bunnySQL, pinSQL
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
            message = (
                await self.client.get_guild(g_id).get_channel(ch_id).fetch_message(m_id)
            )
        except:
            message = None

        return message


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
            await msg.delete()
            await ctx.message.delete()
        else:
            pass


class AutoPinEventHandler(DiscordEventHandler):
    def __init__(self, bot: commands.Bot, app: apps.AutoPinApp):
        self.client = bot
        self.app = app

    # 起動時に動作する処理
    @commands.Cog.listener()
    async def on_ready(self):
        self.clean.start()  # 定期Loopの開始

    # メッセージ受信時に動作する処理
    @commands.Cog.listener("on_message")
    async def message_listener(self, message: discord.Message):
        if message.author.bot:
            return
        else:
            await check_and_activate(message)
        return

    # メッセージ編集時に動作する処理
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        message = await apps.get_message_by_payload(payload)
        if message.author.bot:
            return
        else:
            await check_and_activate(message)
        return

    # メッセージが削除された場合に反応
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        # 削除メッセージがBOTの場合の処理
        _record = pinSQL.select_record_by_post_message(
            payload.message_id, payload.guild_id
        )
        if _record is not None:
            await self.app.sqlIO.deleteHistory_ByRecord(record=_record)
        else:
            pass

        # 削除メッセージがCueの場合の処理
        _record = pinSQL.select_record_by_cue_message(
            payload.message_id, payload.guild_id
        )
        if _record is not None:
            await self.app.__deleteMessage_History_ByRecord(record=_record)
        else:
            pass

    # リアクション追加に対して反応
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        ## ここから完了チェック
        r = pinSQL.select_record_by_cue_message(payload.message_id, payload.guild_id)
        if r is not None:
            cue = await self.app.botIO.getMessage_ByRecord(r, isPost=False)
            if cue is not None:
                if (payload.emoji in g.EMOJI_CHECK) and (
                    payload.user_id == cue.author.id
                ):
                    await self.app.__deleteMessage_History_ByRecord(record=r)
                    return

        ## ここから黒塗りチェック
        elif (
            payload.channel_id == g.guild_channel_map[payload.guild_id]
        ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
            message = await apps.get_message_by_payload(payload)
            if message.author == self.client.user and isFirstReactionAdd(message):
                r = pinSQL.select_record_by_post_message(
                    payload.message_id, g_id=payload.guild_id
                )
                if r is not None:
                    cue = await self.app.botIO.getMessage_ByRecord(r=r, isPost=False)
                    message = await apps.get_message_by_payload(payload)
                    if message.author == self.client.user and isFirstReactionAdd(
                        message
                    ):
                        await autoPin.seal(target=message, base=cue, isSeal=True)
                        return
        return

    # リアクション削除に対して反応
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        ## ここから完了チェック
        try:
            message = await self.client.get_channel(payload.channel_id).fetch_message(
                payload.message_id
            )
        except:
            message = None
        if message is not None:
            if (
                (payload.emoji in g.EMOJI_CHECK)
                and (payload.user_id == message.author.id)
                and await isNoUserCheckReactions(message, payload.user_id)
            ):
                await check_and_activate(message)

        ## ここから黒塗りチェック
        if (
            payload.channel_id == g.guild_channel_map[payload.guild_id]
        ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
            message = await apps.get_message_by_payload(payload)
            if message.author == self.client.user and isNullReaction(message):
                _r = pinSQL.select_record_by_post_message(
                    m_id=message.id, g_id=message.guild.id
                )
                if _r is not None:
                    cue = await self.app.botIO.getMessage_ByRecord(_r, isPost=False)
                    await autoPin.seal(target=message, base=cue, isSeal=False)

    # クリアコマンド
    @commands.command()
    async def clear(self, ctx: commands.Context):
        if ctx.message.content == g.BOT_PREFIX + "clear":  # コマンドだけに限定。
            await apps.clear_user_guild_post(ctx.guild.id, ctx.author.id)
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
            records = SQL.select_records_before_yesterday()
            for r in records:
                message = await self.app.botIO.getMessage_ByRecord(r, isPost=True)
                if (message is not None) and (
                    not isNullReaction(message)
                ):  # Reactionが0じゃなかったら
                    await self.app.__deleteMessage_History_ByRecord(record=r)
                    print("削除 : ", r)
        else:
            pass


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

                await apps.post_bunny(ctx.guild.id, dt_next, seq="interval")

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
        conditions.append(SQLCondition(SQLFields.APP_NAME, self.app.sqlIO.appName))

        rs = self.app.sqlIO.getHistory(conditions=conditions)

        for r in rs:
            await self.app.__deleteMessage_History_ByRecord(record=r)

        now = datetime.now(tz=g.ZONE)
        if 7 <= now.hour and now.hour <= 23:
            await self.app.post_bunny(ctx.guild.id, dt_next, seq)
        else:
            await self.app.post_bunny(ctx.guild.id, dt_next, seq="suspend")


################TEMP###############
client: commands.Bot
autoPin: apps.AutoPinApp


def setClient(c: commands.Bot):
    global client
    global autoPin
    client = c
    apps.setClient(client)
    autoPin = apps.AutoPinApp(pinSQL(), BotMixin(client=client))


################TEMP###############


#########################################
# Local Functions
#########################################


async def check_and_activate(_cue: discord.Message):
    # チェックのリアクションがついている場合、何もしない。
    if not await isNoUserCheckReactions(_cue, _cue.author.id):
        return

    # 投稿済みレコードの検索
    conditions = []
    conditions.append(SQLCondition(SQLFields.CUE_ID, _cue.id))
    conditions.append(SQLCondition(SQLFields.GUILD_ID, _cue.guild.id))
    _record = pinSQL().getHistory(conditions=conditions)

    if _record is None:  # DBに書き込み元メッセージの情報がない場合
        if any((s in _cue.content) for s in g.KEYWORDS_PIN):
            await autoPin.pinToChannel(_cue)
        else:
            pass

    else:  # DBに書き込み元メッセージの情報がある場合
        c_id = g.guild_channel_map[_record.guildID]
        m_id = _record.postID

        try:
            post = await autoPin.botIO.client.get_channel(c_id).fetch_message(m_id)
        except:  # Bot停止中にPostが削除されており、404 Not found.
            post = None

        if any((s in _cue.content) for s in g.KEYWORDS_PIN):
            match post:
                case None:
                    await autoPin.pinToChannel(_cue)
                case case if isNullReaction(case):
                    await autoPin.seal(target=post, base=_cue, isSeal=False)
                case _:
                    await autoPin.seal(target=post, base=_cue, isSeal=True)

        else:  # キーワードが消えてたら、ポストを消し、レコードも消す。
            await autoPin.unpin(record=_record, msg=post)

    return


async def isNoUserCheckReactions(
    message: discord.Message, user: discord.User.id
) -> bool:
    for r in message.reactions:
        reaction_users = [u.id async for u in r.users()]
        if any((s in r.emoji) for s in g.KEYWORDS_CHECK):
            if user in reaction_users:
                return False
    return True


# Reactionチェック
def isNullReaction(message) -> bool:
    return not bool(message.reactions)


def isFirstReactionAdd(message) -> bool:
    return len(message.reactions) == 1 and message.reactions[0].count == 1
