from abc import ABCMeta, abstractmethod
from typing import Union, Optional

import discord
from discord.ext import commands
from myLib.L0_Core.dataTypes import record


#########################################
# Data controller interface
#########################################
class MessageIF(metaclass=ABCMeta):
    client: commands.Bot

    @abstractmethod
    def sendMessage(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        content: Union[str, discord.Embed, list[discord.Embed]],
    ) -> discord.Message:
        pass

    @staticmethod
    @abstractmethod
    async def editMessage(target: discord.Message, embeds: [discord.Embed]):
        pass

    @staticmethod
    @abstractmethod
    async def deleteMessage(msg: discord.Message):
        pass

    @abstractmethod
    async def getMessage_ByRecord(
        self, r: record, isPost: bool = True
    ) -> Optional[discord.Message]:
        pass

    @abstractmethod
    async def getMessage(
        self,
        g_id: discord.Guild.id,
        ch_id: discord.TextChannel.id,
        m_id: discord.Member.id,
    ) -> Optional[discord.Message]:
        pass
