from enum import Enum, auto
from typing import NamedTuple
import discord


#########################################
# Data class
#########################################
class record(NamedTuple):
    postID: discord.Message.id
    cueID: discord.Message.id
    cueChID: discord.TextChannel.id
    createdAt: discord.Message.created_at
    author: discord.Message.author
    guildID: discord.Guild.id
    appName: str


class SQLFields(Enum):
    POST_ID = auto()
    CUE_ID = auto()
    CUE_CH_ID = auto()
    CREATED_AT = auto()
    AUTHOR = auto()
    GUILD_ID = auto()
    APP_NAME = auto()


class SQLCondition(NamedTuple):
    field: SQLFields
    condition: str
