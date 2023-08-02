import sqlite3
import discord

#########################################
# System 環境変数の設定
DB_NAME = "System.db"


#########################################
# データクラス定義
#########################################
class record:
    row = {}

    def __init__(self) -> None:
        self = None

    def __init__(self, post_message_ID, cue_message_ID, created_at, author, guild):
        self.row = {
            "post_message_ID": post_message_ID,
            "cue_message_ID": cue_message_ID,
            "created_at": created_at,
            "author": author,
            "guild": guild,
        }


#########################################
# クエリ
#########################################
CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS
        post_list(
            post_message_ID INTEGER PRIMARY KEY,
            cue_message_ID INTEGER,
            created_at TEXT NOT NULL,
            author INTEGER NOT NULL,
            guild INTEGER NOT NULL
            );
    """
INSERT_RECORDS = """
    INSERT INTO
    post_list (post_message_ID, cue_message_ID, created_at, author, guild)
    VALUES (:post_message_ID, :cue_message_ID, :created_at, :author, :guild);
    """
SELECT_ALL_VALUE = "SELECT * FROM post_list;"
SELECT_GUILD_ALL_VALUE = "SELECT * FROM post_list where guild=:guild;"
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
# SELECT_TYPE_OF_COLUMNS = "SELECT typeof(t1), typeof(t2),typeof(t3),typeof(t4),typeof(t5) FROM example;"


#########################################
# DB操作Function
#########################################
def init():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE)
    conn.commit()
    cur.execute(SELECT_ALL_VALUE)
    for r in cur:
        print(*r)

    conn.close()


def insert_record(cue: discord.Message, post: discord.Message):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    _record = record(post.id, cue.id, cue.created_at, cue.author.id, cue.guild.id)
    cur.execute(INSERT_RECORDS, _record.row)
    conn.commit()
    conn.close()


def select_guild_all_records(g_id) -> list[record]:
    _records = []
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_GUILD_ALL_VALUE, {"guild": g_id})
    for row in cur:
        if row is not None:
            _records.append(record(*row))
    conn.close()
    return _records


def select_record_by_cue_message(
    m_id: discord.Message.id, g_id: discord.Guild.id
) -> record:
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_CUE_MESSAGE, {"ID": m_id, "guild": g_id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


def select_record_by_post_message(
    m_id: discord.Message.id, g_id: discord.Guild.id
) -> record:
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_POST_MESSAGE, {"ID": m_id, "guild": g_id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


## 未使用Funciton
def delete_guild_all_records(guild: discord.guild):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_GUILD_ALL_VALUE, {"guild": guild.id})
    conn.commit()
    conn.close()


#######


def delete_record_by_cue_message(m_id: discord.Message.id, g_id: discord.Guild.id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_CUE_MESSAGE, {"ID": m_id, "guild": g_id})
    conn.commit()
    conn.close()


def delete_record_by_post_message(m_id: discord.Message.id, g_id: discord.Guild.id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_POST_MESSAGE, {"ID": m_id, "guild": g_id})
    conn.commit()
    conn.close()
