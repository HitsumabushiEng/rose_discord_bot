from abc import ABCMeta, abstractmethod
from typing import Optional, Union

import discord

from myLib.L0_Core.dataTypes import record, SQLCondition


#########################################
# Data controller interface
#########################################
class HistoryIF(metaclass=ABCMeta):
    appName: str

    @staticmethod
    @abstractmethod
    def init():
        pass

    @classmethod
    @abstractmethod
    def getHistory(
        cls, conditions: list[SQLCondition]
    ) -> Optional[Union[record, list[record]]]:
        pass

    @classmethod
    @abstractmethod
    def setHistory(cls, post: discord.Message, cue: Optional[discord.Message] = None):
        pass

    @classmethod
    @abstractmethod
    def deleteHistory(cls, conditions: list[SQLCondition]):
        pass

    @classmethod
    @abstractmethod
    def deleteHistory_ByRecord(cls, record: record):
        pass
