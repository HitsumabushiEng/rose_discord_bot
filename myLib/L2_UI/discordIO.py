from typing import Union, Optional

##
import discord
from discord.ext import commands


##
from myLib.L0_Core.messageIF import MessageIF
from myLib.L0_Core.dataTypes import record

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
    async def editMessage(
        target: discord.Message,
        content: Optional[discord.Message.content] = None,
        embeds: Optional[list[discord.Embed]] = None,
    ):
        if content is None and embeds is None:
            return
        elif content is None:
            return await target.edit(embeds=embeds)
        elif embeds is None:
            return await target.edit(content=content)
        else:
            return await target.edit(content=content, embeds=embeds)

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
