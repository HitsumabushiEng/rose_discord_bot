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

#########################################
# System 環境変数の設定
DB_NAME = "System.db"


#########################################
# Data class
#########################################
class record:
    row = {}

    def __init__(self) -> None:
        self = None

    def __init__(
        self,
        post_message_ID,
        cue_message_ID,
        cue_channel_ID,
        created_at,
        author,
        guild,
        app_name,
    ):
        self.row = {
            "post_message_ID": post_message_ID,
            "cue_message_ID": cue_message_ID,
            "cue_channel_ID": cue_channel_ID,
            "created_at": created_at,
            "author": author,
            "guild": guild,
            "app_name": app_name,
        }


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
    where cue_message_ID=:ID AND guild=:guild;
"""
SELECT_VALUE_BY_POST_MESSAGE = """
    SELECT * FROM post_list
    where post_message_ID=:ID AND guild=:guild;
"""

DELETE_GUILD_ALL_VALUE = "DELETE FROM post_list where guild=:guild;"
DELETE_VALUE_BY_CUE_MESSAGE = """
    DELETE FROM post_list
    where cue_message_ID=:ID AND guild=:guild;
"""
DELETE_VALUE_BY_POST_MESSAGE = """
    DELETE FROM post_list
    where post_message_ID=:ID AND guild=:guild;
"""


#########################################
# Super Class
#########################################
class SQL:
    app_name = "default"

    def __init__(self) -> None:
        try:
            self.conn = sqlite3.connect(DB_NAME)
            self.cur = self.conn.cursor()
        except:
            pass

    def __del__(self):
        self.cur.close()

    #########################################
    # DB操作Function
    #########################################
    def init(self):
        self.cur.execute(CREATE_TABLE)
        self.conn.commit()
        self.cur.execute(SELECT_ALL_VALUE)
        for r in self.cur:
            print(*r)

    def insert_record(self, cue: discord.Message, post: discord.Message):
        _record = record(
            post.id,
            cue.id,
            cue.channel.id,
            cue.created_at,
            cue.author.id,
            cue.guild.id,
            self.app_name,
        )

        self.cur.execute(INSERT_RECORDS, _record.row)
        self.conn.commit()

    def select_guild_all_records(self, g_id) -> list[record]:
        _records = []

        self.cur.execute(SELECT_GUILD_ALL_VALUE, {"guild": g_id})
        for row in self.cur:
            if row is not None:
                _records.append(record(*row))
        return _records

    def select_user_guild_records(self, g_id, u_id) -> list[record]:
        _records = []

        self.cur.execute(SELECT_USER_GUILD_VALUE, {"guild": g_id, "author": u_id})
        for row in self.cur:
            if row is not None:
                _records.append(record(*row))
        return _records

    def select_record_by_post_message(
        self, m_id: discord.Message.id, g_id: discord.Guild.id
    ) -> record:
        _record = None

        self.cur.execute(SELECT_VALUE_BY_POST_MESSAGE, {"ID": m_id, "guild": g_id})
        _row = self.cur.fetchone()
        if _row is not None:
            _record = record(*_row)
        return _record

    def select_records_before_yesterday(self) -> list[record]:
        _records = []

        self.cur.execute(SELECT_PAST_RECORDS)
        for row in self.cur:
            if row is not None:
                _records.append(record(*row))
        return _records

    #######

    def delete_record_by_post_message(
        self, m_id: discord.Message.id, g_id: discord.Guild.id
    ):
        self.cur.execute(DELETE_VALUE_BY_POST_MESSAGE, {"ID": m_id, "guild": g_id})
        self.conn.commit()


#########################################
# Sub Class
#########################################
class pinSQL(SQL):
    app_name = "pin"

    #########################################
    # DB操作Function
    #########################################
    def select_record_by_cue_message(
        self, m_id: discord.Message.id, g_id: discord.Guild.id
    ) -> record:
        _record = None

        self.cur.execute(SELECT_VALUE_BY_CUE_MESSAGE, {"ID": m_id, "guild": g_id})
        _row = self.cur.fetchone()
        if _row is not None:
            _record = record(*_row)
        return _record

    def select_records_by_cue_message(
        self, m_id: discord.Message.id, g_id: discord.Guild.id
    ) -> list[record]:
        _records = []

        self.cur.execute(SELECT_VALUE_BY_CUE_MESSAGE, {"ID": m_id, "guild": g_id})
        for row in self.cur:
            if row is not None:
                _records.append(record(*row))
        return _records

    def delete_record_by_cue_message(
        self, m_id: discord.Message.id, g_id: discord.Guild.id
    ):
        self.cur.execute(DELETE_VALUE_BY_CUE_MESSAGE, {"ID": m_id, "guild": g_id})
        self.conn.commit()


class bunnySQL(SQL):
    app_name = "bunny"

    #########################################
    # DB操作Function
    #########################################
    def insert_record(self, post: discord.Message):
        _record = record(
            post.id,
            None,
            None,
            post.created_at,
            post.author.id,
            post.guild.id,
            self.app_name,
        )

        self.cur.execute(INSERT_RECORDS, _record.row)
        self.conn.commit()

    def select_guild_bunny_records(self, g_id) -> list[record]:
        _records = []

        self.cur.execute(SELECT_GUILD_BUNNY_VALUE, {"guild": g_id, "app_name": "bunny"})

        for row in self.cur:
            if row is not None:
                _records.append(record(*row))

        return _records
