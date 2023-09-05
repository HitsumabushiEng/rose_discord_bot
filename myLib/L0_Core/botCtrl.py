from abc import ABCMeta, abstractmethod

import discord
from discord.ext import commands


#########################################
# Data controller interface
#########################################
class BotCtrl(metaclass=ABCMeta):
    client: commands.bot

    @abstractmethod
    def send(
        self, gID: discord.Guild.id, chID: discord.TextChannel.id, content: str
    ) -> discord.Message:
        pass

    @abstractmethod
    async def sendEmbeds(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        embeds: [discord.Embed],
    ) -> discord.Message:
        pass

    @staticmethod
    @abstractmethod
    async def edit(target: discord.Message, embeds: [discord.Embed]):
        pass

    @abstractmethod
    async def deleteMessage(
        self,
        gID: discord.Guild.id,
        chID: discord.TextChannel.id,
        msgID: discord.Message.id,
    ):
        pass
