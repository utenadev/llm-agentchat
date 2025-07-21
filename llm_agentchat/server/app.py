from fastapi import FastAPI, WebSocket, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, List, Any
import llm_agentchat.server.db as db
import datetime
import os

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションの起動時とシャットダウン時に実行されるイベントハンドラ。"""
    # 起動イベント
    # データベースパスはapp.stateから取得
    conn = db.get_db(app.state.db_path)
    db.init_db(conn)
    conn.close()
    yield
    # シャットダウンイベント（ここでは特になし）
    # print("Application is shutting down.")

# FastAPIアプリケーションのインスタンスを作成し、lifespanイベントハンドラを適用
app = FastAPI(lifespan=lifespan)

# プロジェクトのルートディレクトリからの相対パスでstaticディレクトリをマウント
# NOTE: 実際のアプリケーションでは、より堅牢なパス解決が必要になる場合があります
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# WebSocket接続を管理するための辞書
# {room_name: {agent_name: websocket}}
active_connections: Dict[str, Dict[str, WebSocket]] = {}

# データベースのパスはapp.stateから取得するように変更
# DATABASE_PATH = "chat_history.db" # この行は削除またはコメントアウト

# lifespan関数は既に定義されているため、ここでは変更なし

async def broadcast_message(room: str, message: Dict[str, Any]):
    """
    指定されたルームの全てのWebSocketクライアントにメッセージをブロードキャストします。
    """
    if room in active_connections:
        # 接続リストをコピーして、非同期イテレーション中にリストが変更されるのを防ぐ
        connections_to_remove = []
        # エージェント名と接続のペアをイテレート
        for agent_name, connection in list(active_connections[room].items()):
            try:
                await connection.send_json(message)
            except Exception as e:
                # 送信失敗した接続はクローズされたとみなし、リストから削除
                print(f"Error broadcasting message to {agent_name}: {e}")
                connections_to_remove.append(agent_name)
        for agent_name in connections_to_remove:
            if agent_name in active_connections[room]:
                del active_connections[room][agent_name]

@app.get("/api/messages", response_model=List[Dict[str, Any]])
async def get_messages(room: str):
    """
    特定のチャットルームの過去のメッセージを取得します。
    """
    # app.state.db_pathからデータベースパスを取得
    conn = db.get_db(app.state.db_path)
    messages_from_db = db.get_messages_for_room(conn, room)
    conn.close()
    # フロントエンドが期待する 'message' キーに 'message_content' をマッピング
    messages = [
        {
            "room": msg.get("room_name"),
            "sender": msg.get("sender"),
            "message": msg.get("message_content"),
            "timestamp": msg.get("timestamp"),
            "type": msg.get("message_type"),
        }
        for msg in messages_from_db
    ]
    return messages

@app.post("/api/message")
async def post_message(message: Dict[str, Any]):
    """
    新しいメッセージを投稿し、データベースに保存してWebSocketクライアントにブロードキャストします。
    """
    room = message.get("room")
    sender = message.get("sender")
    message_content = message.get("message")
    message_type = message.get("type", "chat") # デフォルトは'chat'
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not all([room, sender, message_content]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing room, sender, or message"
        )

    # app.state.db_pathからデータベースパスを取得
    conn = db.get_db(app.state.db_path)
    db.add_message(conn, room, sender, message_content, message_type, timestamp)
    conn.close()

    full_message = {
        "room": room,
        "sender": sender,
        "message": message_content,
        "timestamp": timestamp,
        "type": message_type
    }
    await broadcast_message(room, full_message)
    return {"status": "ok"}

@app.get("/api/agents")
async def get_agents(room: str):
    """
    指定されたチャットルームに参加しているエージェントのリストを取得します。
    """
    if room not in active_connections:
        return []
    # agent_name のリストを返す
    return list(active_connections[room].keys())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, room: str, agent: str = "human"):
    """
    WebSocket接続を処理し、リアルタイムメッセージ通信を可能にします。
    agentクエリパラメータを受け取るように変更。
    """
    await websocket.accept()
    if room not in active_connections:
        active_connections[room] = {}
    active_connections[room][agent] = websocket
    print(f"WebSocket connected: {agent} to room '{room}'")

    # 接続時に既存のメッセージを送信（オプション、Web UIがGET /api/messagesを呼ぶためここでは不要）

    try:
        while True:
            # クライアントからのメッセージをリッスン（エージェントが利用）
            data = await websocket.receive_json()
            
            # WebSocket経由で受信したメッセージにもタイムスタンプを追加し、完全なメッセージオブジェクトを構築
            received_room = data.get("room", room)
            sender = data.get("sender", "unknown")
            message_content = data.get("message", "")
            message_type = data.get("type", "chat")
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            full_message = {
                "room": received_room,
                "sender": sender,
                "message": message_content,
                "timestamp": timestamp,
                "type": message_type
            }
            
            # データベースに保存（WebSocket経由のメッセージも保存する）
            # app.state.db_pathからデータベースパスを取得
            conn = db.get_db(app.state.db_path)
            db.add_message(conn, received_room, sender, message_content, message_type, timestamp)
            conn.close()

            # 受信したメッセージを他のクライアントにブロードキャスト
            await broadcast_message(received_room, full_message)

    except Exception as e:
            print(f"WebSocket disconnected from room '{room}' agent '{agent}': {e}")
    finally:
            # 接続がクローズされたら辞書から削除
            if room in active_connections and agent in active_connections[room]:
                del active_connections[room][agent]
                if not active_connections[room]:
                    del active_connections[room]

# 静的ファイルを提供するための設定
# この行は、他の具体的なルート（/api/*, /ws）の後に置く必要があります。
# これにより、FastAPIはまずAPIルートをチェックし、一致しない場合に静的ファイルとして処理しようとします。
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
