#########################################
# DB関係のクラス。
#
# DBの構築、DBに関するI/Fを定義
#
# DB List
#
# Table :
#   post_list
# Data：
#   post_message_ID INTEGER     PRIMARY KEY,
#   cue_message_ID  INTEGER     # Null for bunny
#   cue_channel_ID  INTEGER     # Null for bunny
#   created_at      TEXT        NOT NULL,
#   author          INTEGER     NOT NULL,
#   guild           INTEGER     NOT NULL,
#   app_name        TEXT        NOT NULL,
#
#########################################
import sqlite3
import discord
from contextlib import closing
from typing import Union, Optional
from enum import Enum, auto

from myLib.L0_Core.historyCtrl import HistoryCtrl
from myLib.L0_Core.dataTypes import record, SQLCondition, SQLFields

#########################################
# System 環境変数の設定
DB_NAME = "System.db"

#########################################
# Enum
#########################################
sqliteFieldName = {
    SQLFields.POST_ID: "post_message_ID",
    SQLFields.CUE_ID: "cue_message_ID",
    SQLFields.CUE_CH_ID: "cue_channel_ID",
    SQLFields.CREATED_AT: "created_at",
    SQLFields.AUTHOR: "author",
    SQLFields.GUILD_ID: "guild",
    SQLFields.APP_NAME: "app_name",
}


class AppNames(Enum):
    AUTO_PIN = "pin"
    BUNNY_TIMER = "bunny"


class Queries(Enum):
    CREATE_TABLE = auto()
    INSERT_RECORDS = auto()
    SELECT_ALL_VALUE = auto()
    SELECT_PAST_RECORDS = auto()
    SELECT_GUILD_ALL_VALUE = auto()
    SELECT_GUILD_BUNNY_VALUE = auto()
    SELECT_USER_GUILD_VALUE = auto()
    SELECT_VALUE_BY_CUE_MESSAGE = auto()
    SELECT_VALUE_BY_POST_MESSAGE = auto()
    DELETE_VALUE_BY_POST_MESSAGE = auto()


#########################################
# クエリ
#########################################
CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS
        post_list(
            post_message_ID INTEGER PRIMARY KEY,
            cue_message_ID INTEGER,
            cue_channel_ID INTEGER,
            created_at TEXT NOT NULL,
            author INTEGER NOT NULL,
            guild INTEGER NOT NULL,
            app_name TEXT NOT NULL
            );
    """
INSERT_RECORDS = """
    INSERT INTO
    post_list (post_message_ID, cue_message_ID, cue_channel_ID, created_at, author, guild, app_name)
    VALUES (:post_message_ID, :cue_message_ID, :cue_channel_ID, :created_at, :author, :guild,:app_name);
    """

SELECT_ALL_VALUE = "SELECT * FROM post_list;"
SELECT_PAST_RECORDS = (
    "SELECT * FROM post_list WHERE created_at < datetime('now','-4 hours');"
)
SELECT_GUILD_ALL_VALUE = "SELECT * FROM post_list where guild=:guild;"
SELECT_GUILD_BUNNY_VALUE = (
    "SELECT * FROM post_list where guild=:guild AND app_name=:app_name;"
)
SELECT_USER_GUILD_VALUE = (
    "SELECT * FROM post_list where guild=:guild AND author=:author;"
)
SELECT_VALUE_BY_CUE_MESSAGE = """
    SELECT * FROM post_list
    where cue_message_ID=:cue_message_ID AND guild=:guild;
"""
SELECT_VALUE_BY_POST_MESSAGE = """
    SELECT * FROM post_list
    where post_message_ID=:post_message_ID AND guild=:guild;
"""

DELETE_VALUE_BY_POST_MESSAGE = """
    DELETE FROM post_list
    where post_message_ID=:post_message_ID AND guild=:guild;
"""


#########################################
# Local function
#########################################
def query_of_getHistory(conditions: list[SQLCondition]) -> Optional[Queries]:
    match dict(conditions):
        case x if len(x) == 1 and SQLFields.CREATED_AT in x.keys():
            return Queries.SELECT_PAST_RECORDS

        case x if len(x) == 1 and SQLFields.GUILD_ID in x.keys():
            return Queries.SELECT_GUILD_ALL_VALUE

        case x if len(x) == 2 and SQLFields.APP_NAME in x.keys():
            return Queries.SELECT_GUILD_BUNNY_VALUE

        case x if len(x) == 2 and SQLFields.AUTHOR in x.keys():
            return Queries.SELECT_USER_GUILD_VALUE

        case x if len(x) == 2 and SQLFields.CUE_ID in x.keys():
            return Queries.SELECT_VALUE_BY_CUE_MESSAGE

        case x if len(x) == 2 and SQLFields.POST_ID in x.keys():
            return Queries.SELECT_VALUE_BY_POST_MESSAGE

        case _:
            return None


#########################################
# Super Class
#########################################
class SQL(HistoryCtrl):
    appName = "default"

    def __init__(self) -> None:
        pass

    def __del__(self):
        pass

    #########################################
    # Implement interface functions
    #########################################
    @staticmethod
    def init():
        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(CREATE_TABLE)
            con.commit()
            cur.execute(SELECT_ALL_VALUE)
            for r in cur:
                print(*r)

    #########################################
    # There are some sub-class which extend this class.
    # Sub-class unique function should be routed via each sub-class
    #########################################
    @classmethod
    def getHistory(
        cls, conditions: list[SQLCondition]
    ) -> Optional[Union[record, list[record]]]:
        query = query_of_getHistory(conditions)
        d = dict(conditions)

        match query:
            case Queries.SELECT_PAST_RECORDS:
                return cls.select_records_before_yesterday()

            case Queries.SELECT_GUILD_ALL_VALUE:
                return cls.select_guild_all_records(d.get(SQLFields.GUILD_ID))

            case Queries.SELECT_USER_GUILD_VALUE:
                return cls.select_user_guild_records(
                    g_id=d.get(SQLFields.GUILD_ID),
                    u_id=d.get(SQLFields.AUTHOR),
                )

            case Queries.SELECT_VALUE_BY_POST_MESSAGE:
                return cls.select_record_by_post_message(
                    g_id=d.get(SQLFields.GUILD_ID),
                    m_id=d.get(SQLFields.POST_ID),
                )

            case _:
                return None

    @classmethod
    def setHistory(cls, post: discord.Message, cue: Optional[discord.Message] = None):
        return cls.insert_record(post=post, cue=cue)

    @classmethod
    def deleteHistory(cls, conditions: list[SQLCondition]):
        d = dict(conditions)
        return cls.delete_record_by_post_message(
            m_id=d.get(SQLFields.POST_ID), g_id=d.get(SQLFields.GUILD_ID)
        )

    #########################################
    # DB操作Function
    #########################################
    @classmethod
    def insert_record(cls, post: discord.Message, cue: discord.Message):
        match cue:
            case None:  # for Bunny and error case
                _record = record(
                    post.id,
                    None,
                    None,
                    post.created_at,
                    post.author.id,
                    post.guild.id,
                    cls.appName,
                )
            case _:  # for pin
                _record = record(
                    post.id,
                    cue.id,
                    cue.channel.id,
                    cue.created_at,
                    cue.author.id,
                    cue.guild.id,
                    cls.appName,
                )

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(INSERT_RECORDS, _record)
            con.commit()

    @staticmethod
    def select_guild_all_records(g_id) -> list[record]:
        _records = []

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                SELECT_GUILD_ALL_VALUE, {sqliteFieldName.get(SQLFields.GUILD_ID): g_id}
            )
            for row in cur:
                if row is not None:
                    _records.append(record(*row))
        return _records

    @staticmethod
    def select_user_guild_records(
        g_id: discord.Guild.id, u_id: discord.Member.id
    ) -> list[record]:
        _records = []

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                SELECT_USER_GUILD_VALUE,
                {
                    sqliteFieldName.get(SQLFields.GUILD_ID): g_id,
                    sqliteFieldName.get(SQLFields.AUTHOR): u_id,
                },
            )
            for row in cur:
                if row is not None:
                    _records.append(record(*row))
        return _records

    @staticmethod
    def select_record_by_post_message(
        m_id: discord.Message.id, g_id: discord.Guild.id
    ) -> Optional[record]:
        _record = None

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                SELECT_VALUE_BY_POST_MESSAGE,
                {
                    sqliteFieldName.get(SQLFields.POST_ID): m_id,
                    sqliteFieldName.get(SQLFields.GUILD_ID): g_id,
                },
            )
            _row = cur.fetchone()
            if _row is not None:
                _record = record(*_row)
        return _record

    @staticmethod
    def select_records_before_yesterday() -> Optional[list[record]]:
        _records = []

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(SELECT_PAST_RECORDS)
            for row in cur:
                if row is not None:
                    _records.append(record(*row))
        return _records

    #######

    @staticmethod
    def delete_record_by_post_message(m_id: discord.Message.id, g_id: discord.Guild.id):
        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                DELETE_VALUE_BY_POST_MESSAGE,
                {
                    sqliteFieldName.get(SQLFields.POST_ID): m_id,
                    sqliteFieldName.get(SQLFields.GUILD_ID): g_id,
                },
            )
            con.commit()


#########################################
# Sub Class
#########################################
class pinSQL(SQL):
    appName = AppNames.AUTO_PIN.value

    @classmethod
    def getHistory(
        cls, conditions: list[SQLCondition]
    ) -> Optional[Union[record, list[record]]]:
        query = query_of_getHistory(conditions)
        d = dict(conditions)

        match query:
            case Queries.SELECT_VALUE_BY_CUE_MESSAGE:
                return cls.select_record_by_cue_message(
                    g_id=d.get(SQLFields.GUILD_ID),
                    m_id=d.get(SQLFields.CUE_ID),
                )
            case _:
                return super().getHistory(conditions)

    @staticmethod
    def select_record_by_cue_message(
        m_id: discord.Message.id, g_id: discord.Guild.id
    ) -> record:
        _record = None

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                SELECT_VALUE_BY_CUE_MESSAGE,
                {
                    sqliteFieldName.get(SQLFields.CUE_ID): m_id,
                    sqliteFieldName.get(SQLFields.GUILD_ID): g_id,
                },
            )
            _row = cur.fetchone()
            if _row is not None:
                _record = record(*_row)
        return _record


class bunnySQL(SQL):
    appName = AppNames.BUNNY_TIMER.value

    @classmethod
    def getHistory(
        cls, conditions: list[SQLCondition]
    ) -> Optional[Union[record, list[record]]]:
        query = query_of_getHistory(conditions)
        d = dict(conditions)

        match query:
            case Queries.SELECT_GUILD_BUNNY_VALUES:
                return cls.select_guild_bunny_records(g_id=d.get(SQLFields.GUILD_ID))
            case _:
                return super().getHistory(conditions)

    @staticmethod
    def select_guild_bunny_records(g_id: discord.Guild.id) -> list[record]:
        _records = []

        with closing(sqlite3.connect(DB_NAME)) as con:
            cur = con.cursor()
            cur.execute(
                SELECT_GUILD_BUNNY_VALUE,
                {
                    sqliteFieldName.get(SQLFields.GUILD_ID): g_id,
                    sqliteFieldName.get(SQLFields.APP_NAME): AppNames.BUNNY_TIMER.value,
                },
            )

            for row in cur:
                if row is not None:
                    _records.append(record(*row))

        return _records
