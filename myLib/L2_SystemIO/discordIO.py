import os
import asyncio

##
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import re

from discord.guild import Guild

##
from myLib.L0_Core.botCtrl import BotCtrl
from myLib.L2_SystemIO.sql import SQL, bunnySQL, pinSQL
import myLib.L1_Apps.apps as apps
import myLib.L1_Apps.setting as g


# Intents / Client の設定 / channel初期化
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
client = commands.Bot(command_prefix=g.BOT_PREFIX, intents=intents)
apps.setClient(client)


class Bot(BotCtrl):
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


class EventHandler:
    def __init__(self, client: commands.Bot) -> None:
        self.client = client

    def __del__(self) -> None:
        pass


# AutoPin アプリのインスタンス化
autoPin = apps.AutoPin(pinSQL(), Bot(client=client))


# 起動時に動作する処理
@client.event
async def on_ready():
    # 参加している各ギルドの書き込み対象chを取得、保持
    guilds = client.guilds

    if guilds is not None:
        for g in guilds:
            apps.register_guild_ch(g)

    clean.start()  # 定期Loopの開始

    print("Test Bot logged in")


# クライアントに追加 / 削除時に反応
@client.event
async def on_guild_join(guild: discord.guild):
    apps.register_guild_ch(guild)


@client.event
async def on_guild_remove(guild: discord.guild):
    await apps.clear_guild_all_post(guild.id)
    apps.erase_guild_ch(guild.id)


# メッセージ受信時に動作する処理
@client.listen("on_message")
async def message_listener(message: discord.Message):
    if message.author.bot:
        return
    else:
        await autoPin.check_and_activate(message)
    return


# メッセージ編集時に動作する処理
@client.event
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    message = await apps.get_message_by_payload(payload)
    if message.author.bot:
        return
    else:
        await autoPin.check_and_activate(message)
    return


# メッセージが削除された場合に反応
@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    # 削除メッセージがBOTの場合の処理
    _record = pinSQL.select_record_by_post_message(payload.message_id, payload.guild_id)
    if _record is not None:
        await apps.delete_post_by_record(_record, POST=False, DB=True)
    else:
        pass

    # 削除メッセージがCueの場合の処理
    _record = pinSQL.select_record_by_cue_message(payload.message_id, payload.guild_id)
    if _record is not None:
        await apps.delete_post_by_record(_record, POST=True, DB=True)
    else:
        pass


# リアクション追加に対して反応
@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    ## ここから完了チェック
    r = pinSQL.select_record_by_cue_message(payload.message_id, payload.guild_id)
    if r is not None:
        cue = await apps.get_message_by_record(r, isPost=False)
        if cue is not None:
            if (payload.emoji in g.EMOJI_CHECK) and (payload.user_id == cue.author.id):
                await apps.delete_post_by_record(r=r, POST=True, DB=True)
                return

    ## ここから黒塗りチェック
    elif (
        payload.channel_id == g.guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await apps.get_message_by_payload(payload)
        if message.author == client.user and apps.isFirstReactionAdd(message):
            r = pinSQL.select_record_by_post_message(
                payload.message_id, g_id=payload.guild_id
            )
            if r is not None:
                cue = await apps.get_message_by_record(r=r, isPost=False)
                message = await apps.get_message_by_payload(payload)
                if message.author == client.user and apps.isFirstReactionAdd(message):
                    await autoPin.seal(target=message, base=cue, isSeal=True)
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
            (payload.emoji in g.EMOJI_CHECK)
            and (payload.user_id == message.author.id)
            and await apps.isNoUserCheckReactions(message, payload.user_id)
        ):
            await autoPin.check_and_activate(message)

    ## ここから黒塗りチェック
    if (
        payload.channel_id == g.guild_channel_map[payload.guild_id]
    ):  # なくてもいいけど、あればHTTPリクエストなしでフィルタできる。
        message = await apps.get_message_by_payload(payload)
        if message.author == client.user and apps.isNullReaction(message):
            _r = pinSQL.select_record_by_post_message(
                m_id=message.id, g_id=message.guild.id
            )
            if _r is not None:
                cue = await apps.get_message_by_record(_r, isPost=False)
                await autoPin.seal(target=message, base=cue, isSeal=False)


# クリアコマンド
@client.command()
async def clear(ctx: commands.Context):
    if ctx.message.content == g.BOT_PREFIX + "clear":  # コマンドだけに限定。
        await apps.clear_user_guild_post(ctx.guild.id, ctx.author.id)
        msg = await ctx.send("--- your posts cleared ---")
        await asyncio.sleep(g.COMMAND_FB_TIME)
        await msg.delete()
        await ctx.message.delete()
    else:
        pass


@client.command()
@commands.has_permissions(manage_messages=True)
async def clear_all(ctx: commands.Context):
    if ctx.message.content == g.BOT_PREFIX + "clear_all":  # コマンドだけに限定。
        await apps.clear_guild_all_post(ctx.guild.id)
        msg = await ctx.send("--- all posts cleared ---")
        await asyncio.sleep(g.COMMAND_FB_TIME)
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
            dt_next = datetime.now(tz=g.ZONE) + t_delta

            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

            usagi.change_interval(time=next)

            await apps.post_bunny(ctx.guild.id, dt_next, seq="interval")

            try:
                usagi.start(ctx, "on_bunny")
            except:
                usagi.restart(ctx, "on_bunny")

        else:
            msg = await ctx.send(g.CAUTION_COMMAND_ERROR)
            await asyncio.sleep(g.COMMAND_FB_TIME)
            await msg.delete()

    await ctx.message.delete()

    return


#########################################
# 定期実行ルーチン
#########################################


# 自動消去ルーチン
@tasks.loop(time=g.CLEAN_TIME, reconnect=True)
async def clean():
    now = datetime.now(tz=g.ZONE)

    if now.weekday() % 7 == g.CLEAN_DAY and g.CLEAN_ACTIVE:  # 決まった曜日のみ実行
        print("定期動作作動")
        records = SQL.select_records_before_yesterday()
        for r in records:
            message = await apps.get_message_by_record(r, isPost=True)
            if (message is not None) and (
                not apps.isNullReaction(message)
            ):  # Reactionが0じゃなかったら
                await apps.delete_post_by_record(r, POST=True, DB=True)
                print("削除 : ", r)
    else:
        pass


# @tasks.loop(seconds=10, reconnect=True, count=3)
@tasks.loop(hours=30, reconnect=True, count=5)
async def usagi(ctx: commands.Context, seq: str):
    match seq:
        case "on_bunny":
            dt_next = datetime.now(tz=g.ZONE) + timedelta(minutes=10)
            # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=1)
            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

            await bunny_message_manage(ctx, dt_next, seq)

            usagi.change_interval(time=next)
            usagi.restart(ctx, "interval")

        case "interval":
            dt_next = datetime.now(tz=g.ZONE) + timedelta(hours=1, minutes=30)
            # dt_next = datetime.now(tz=ZONE) + timedelta(minutes=2)
            next = time(hour=dt_next.hour, minute=dt_next.minute, tzinfo=g.ZONE)

            await bunny_message_manage(ctx, dt_next, seq)

            usagi.change_interval(time=next)
            usagi.restart(ctx, "on_bunny")

        case _:
            usagi.cancel()
            print(g.ERROR_MESSAGE.format("うさぎタイマー"))


async def bunny_message_manage(ctx: commands.Context, dt_next: datetime, seq: str):
    rs = bunnySQL.select_guild_bunny_records(g_id=ctx.guild.id)
    for r in rs:
        await apps.delete_post_by_record(r, POST=True, DB=True)

    now = datetime.now(tz=g.ZONE)
    if 7 <= now.hour and now.hour <= 23:
        await apps.post_bunny(ctx.guild.id, dt_next, seq)
    else:
        await apps.post_bunny(ctx.guild.id, dt_next, seq="suspend")


#########################################
# Client起動
#########################################


# Botの起動とDiscordサーバーへの接続
def activate_client(DEBUG_MODE):
    match DEBUG_MODE:
        case "Deploy":
            TOKEN = os.getenv("TOKEN")
        case "Rose_dev":
            tObj = open("token")  # for Rose
            TOKEN = tObj.read()
        case "Earnest_dev":
            tObj = open("token_dev")  # for Earnest
            TOKEN = tObj.read()
        case _:
            tObj = open("token_dev")  # for Earnest
            TOKEN = tObj.read()

    client.run(TOKEN)
