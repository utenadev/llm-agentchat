import pytest
import sqlite3
import datetime

# NOTE: このテストファイルは、プロジェクトの設計ドキュメントに基づいたスケルトンです。
# `llm_agentchat.server.db`モジュールが実装されている必要があります。
try:
    from llm_agentchat.server import db
except (ImportError, ModuleNotFoundError):
    db = None

@pytest.fixture
def memory_db():
    """テスト用にインメモリSQLiteデータベースをセットアップするフィクスチャ。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 他のテストのために、手動でテーブルを作成します。
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
    conn.commit()
    yield conn
    conn.close()

@pytest.mark.skipif(db is None, reason="llm_agentchat.server.db module not found")
def test_add_message(memory_db):
    """db.add_messageが正しく行を挿入するかをテストします。"""
    conn = memory_db
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # db.add_messageを呼び出します（実装されていると仮定）
    db.add_message(
        conn=conn,
        room_name="test-room",
        sender="tester",
        message="hello world",
        message_type="chat",
        timestamp=timestamp
    )

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE sender = 'tester'")
    row = cursor.fetchone()
    
    assert row is not None
    assert row[1] == "test-room"
    assert row[2] == "tester"
    assert row[3] == "hello world"
    assert row[4] == timestamp
    assert row[5] == "chat"

@pytest.mark.skipif(db is None, reason="llm_agentchat.server.db module not found")
def test_get_messages_for_room(memory_db):
    """db.get_messages_for_roomが正しいメッセージを取得するかをテストします。"""
    conn = memory_db
    # get_messagesをテストするために手動でデータを挿入します
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages VALUES (NULL, 'room1', 'agent1', 'msg1', '2023-01-01T12:00:00Z', 'chat')")
    cursor.execute("INSERT INTO messages VALUES (NULL, 'room2', 'agent2', 'msg2', '2023-01-01T12:01:00Z', 'chat')")
    cursor.execute("INSERT INTO messages VALUES (NULL, 'room1', 'agent3', 'msg3', '2023-01-01T12:02:00Z', 'chat')")
    conn.commit()

    messages = db.get_messages_for_room(conn, "room1")
    
    assert len(messages) == 2
    assert messages[0]["sender"] == "agent1"
    assert messages[1]["sender"] == "agent3"
