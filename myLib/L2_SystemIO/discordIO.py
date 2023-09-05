import asyncio

##
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import re

from discord.guild import Guild

##
from myLib.L0_Core.botCtrl import BotCtrl
from myLib.L0_Core.dataTypes import SQLCondition, SQLFields

from myLib.L2_SystemIO.sql import SQL, bunnySQL, pinSQL
import myLib.L1_Apps.apps as apps
import myLib.L1_Apps.setting as g


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    # 起動時に動作する処理
    @commands.Cog.listener()
    async def on_ready(self):
        # 参加している各ギルドの書き込み対象chを取得、保持
        guilds = self.client.guilds

        if guilds is not None:
            for g in guilds:
                register_guild_ch(g)

        print("Test Bot logged in")

    # クライアントに追加 / 削除時に反応
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.guild):
        register_guild_ch(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.guild):
        await apps.clear_guild_all_post(guild.id)
        erase_guild_ch(guild.id)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear_all(self, ctx: commands.Context):
        if ctx.message.content == g.BOT_PREFIX + "clear_all":  # コマンドだけに限定。
            await apps.clear_guild_all_post(ctx.guild.id)
            msg = await ctx.send("--- all posts cleared ---")
            await asyncio.sleep(g.COMMAND_FB_TIME)
            await msg.delete()
            await ctx.message.delete()
        else:
            pass


class AutoPinCog(commands.Cog):
    def __init__(self, bot):
        self.client = bot

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
            await apps.delete_post_by_record(_record, POST=False, DB=True)
        else:
            pass

        # 削除メッセージがCueの場合の処理
        _record = pinSQL.select_record_by_cue_message(
            payload.message_id, payload.guild_id
        )
        if _record is not None:
            await apps.delete_post_by_record(_record, POST=True, DB=True)
        else:
            pass

    # リアクション追加に対して反応
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        ## ここから完了チェック
        r = pinSQL.select_record_by_cue_message(payload.message_id, payload.guild_id)
        if r is not None:
            cue = await apps.get_message_by_record(r, isPost=False)
            if cue is not None:
                if (payload.emoji in g.EMOJI_CHECK) and (
                    payload.user_id == cue.author.id
                ):
                    await apps.delete_post_by_record(r=r, POST=True, DB=True)
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
                    cue = await apps.get_message_by_record(r=r, isPost=False)
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
                    cue = await apps.get_message_by_record(_r, isPost=False)
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
                message = await apps.get_message_by_record(r, isPost=True)
                if (message is not None) and (
                    not isNullReaction(message)
                ):  # Reactionが0じゃなかったら
                    await apps.delete_post_by_record(r, POST=True, DB=True)
                    print("削除 : ", r)
        else:
            pass


class BunnyTimerCog(commands.Cog):
    def __init__(self, bot):
        self.client = bot

    # ウサギさんタイマーコマンド
    @commands.command()
    async def usagi(self, ctx: commands.Context):
        if "stop" in ctx.message.content:
            await bunny_message_manage(ctx, datetime.now(), "suspend")
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

                await bunny_message_manage(ctx, dt_next, seq)

                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, "interval")

            case "interval":
                dt_next = datetime.now(tz=g.ZONE) + timedelta(hours=1, minutes=30)
                # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=2)
                next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

                await bunny_message_manage(ctx, dt_next, seq)

                self.usagi_loop.change_interval(time=next)
                self.usagi_loop.restart(ctx, "on_bunny")

            case _:
                self.usagi_loop.cancel()
                print(g.ERROR_MESSAGE.format("うさぎタイマー"))


class myBot(BotCtrl):
    client: commands.Bot

    def __init__(self, client: commands.Bot) -> None:
        self.client = client
        pass

    def __del__(self) -> None:
        pass

    async def send(
        self, gID: discord.Guild.id, chID: discord.TextChannel.id, content: str
    ) -> discord.Message:
        return await self.client.get_guild(gID).get_channel(chID).send(content=content)

    async def sendEmbeds(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        embeds: [discord.Embed],
    ) -> discord.Message:
        return await self.client.get_guild(gID).get_channel(chID).send(embeds=embeds)

    @staticmethod
    async def edit(target: discord.Message, embeds: [discord.Embed]):
        await target.edit(embeds=embeds)

    async def deleteMessage(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        msgID: discord.Message.id,
    ):
        try:
            msg = (
                await self.client.get_guild(gID).get_channel(chID).fetch_message(msgID)
            )
        except:
            msg = None
        if msg is not None:
            await msg.delete()


################TEMP###############
client: commands.Bot
autoPin: apps.AutoPin


def setClient(c: commands.Bot):
    global client
    global autoPin
    client = c
    apps.setClient(client)
    autoPin = apps.AutoPin(pinSQL(), myBot(client=client))


################TEMP###############


#########################################
# Local Functions
#########################################


async def bunny_message_manage(ctx: commands.Context, dt_next: datetime, seq: str):
    rs = bunnySQL.select_guild_bunny_records(g_id=ctx.guild.id)
    for r in rs:
        await apps.delete_post_by_record(r, POST=True, DB=True)

    now = datetime.now(tz=g.ZONE)
    if 7 <= now.hour and now.hour <= 23:
        await apps.post_bunny(ctx.guild.id, dt_next, seq)
    else:
        await apps.post_bunny(ctx.guild.id, dt_next, seq="suspend")


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
            await autoPin.unpin(_record)

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


def register_guild_ch(_g: discord.Guild):
    for c in _g.channels:
        if c.name == g.CHANNEL:
            ## guild id -> channel を紐づけ
            g.guild_channel_map[_g.id] = c.id


def erase_guild_ch(_gid: discord.Guild.id):
    del g.guild_channel_map[_gid]
