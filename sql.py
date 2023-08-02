import sqlite3

#########################################
# System 環境変数の設定
DB_NAME = "System.db"


#########################################
# データクラス定義
#########################################
class record:
    row = {}

    def __init__(self):
        self.row = {}

    def __init__(self, post_message_ID, cue_message_ID, created_at, author):
        self.row = {
            "post_message_ID": post_message_ID,
            "cue_message_ID": cue_message_ID,
            "created_at": created_at,
            "author": author,
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
            author INTEGER NOT NULL)
    """
INSERT_RECORDS = """
    INSERT INTO
    post_list (post_message_ID, cue_message_ID, created_at, author)
    VALUES (:post_message_ID, :cue_message_ID, :created_at, :author);
    """
SELECT_ALL_VALUE = "SELECT * FROM post_list;"
SELECT_VALUE_BY_CUE_MESSAGE_ID = """
    SELECT * FROM post_list
    where cue_message_ID=:ID;
"""
SELECT_VALUE_BY_POST_MESSAGE_ID = """
    SELECT * FROM post_list
    where post_message_ID=:ID;
"""
DELETE_ALL_VALUE = "DELETE FROM post_list;"
DELETE_VALUE_BY_CUE_MESSAGE_ID = """
    DELETE FROM post_list
    where cue_message_ID=:ID;
"""
DELETE_VALUE_BY_POST_MESSAGE_ID = """
    DELETE FROM post_list
    where post_message_ID=:ID;
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


def insert_record(cue, post):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    _record = record(post.id, cue.id, cue.created_at, cue.author.id)
    cur.execute(INSERT_RECORDS, _record.row)
    conn.commit()
    conn.close()


def select_all_records() -> list[record]:
    _records = []
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_ALL_VALUE)
    for row in cur:
        if row is not None:
            _records.append(record(*row))
    conn.close()
    return _records


def select_record_by_cue_message_id(id) -> record:
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_CUE_MESSAGE_ID, {"ID": id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


def select_record_by_post_message_id(id) -> record:
    _record = None
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(SELECT_VALUE_BY_POST_MESSAGE_ID, {"ID": id})
    _row = cur.fetchone()
    if _row is not None:
        _record = record(*_row)
    conn.close()
    return _record


def delete_all_records():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_ALL_VALUE)
    conn.commit()
    conn.close()


def delete_record_by_cue_message_id(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_CUE_MESSAGE_ID, {"ID": id})
    conn.commit()
    conn.close()


def delete_record_by_post_message_id(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(DELETE_VALUE_BY_POST_MESSAGE_ID, {"ID": id})
    conn.commit()
    conn.close()
