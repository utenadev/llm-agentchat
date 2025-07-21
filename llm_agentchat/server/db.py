import sqlite3
import datetime
from typing import List, Dict, Any

def get_db(db_path: str) -> sqlite3.Connection:
    """データベース接続を取得します。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection):
    """データベースのテーブルを初期化します。"""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_name TEXT NOT NULL,
        sender TEXT NOT NULL,
        message_content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        message_type TEXT NOT NULL
    )
    """)
    # メッセージ検索を高速化するためのインデックスを作成
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_room_name_timestamp ON messages (room_name, timestamp)")
    conn.commit()

def add_message(conn: sqlite3.Connection, room_name: str, sender: str, message: str, message_type: str, timestamp: str):
    """メッセージをデータベースに追加します。"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (room_name, sender, message_content, message_type, timestamp) VALUES (?, ?, ?, ?, ?)",
        (room_name, sender, message, message_type, timestamp)
    )
    conn.commit()

def get_messages_for_room(conn: sqlite3.Connection, room_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """指定されたルームのメッセージを取得します。"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, message_content, timestamp, message_type FROM messages WHERE room_name = ? ORDER BY timestamp ASC LIMIT ?",
        (room_name, limit)
    )
    # sqlite3.Rowオブジェクトを辞書に変換します
    messages = [dict(row) for row in cursor.fetchall()]
    return messages
