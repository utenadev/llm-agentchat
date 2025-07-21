# WebSocketクライアントの実装
import websockets
import json
import asyncio
from typing import Callable, Any, Dict # Dict をインポートに追加

class WebSocketClient:
    """
    WebSocketサーバーに接続し、メッセージを送受信するためのクライアント。
    """
    def __init__(self, server_url: str, room_name: str, agent_name: str, on_message: Callable[[Dict[str, Any]], None]):
        self.server_url = server_url
        self.room_name = room_name
        self.agent_name = agent_name
        self.on_message = on_message # 受信メッセージを処理するコールバック
        self.websocket = None
        self._listener_task = None
        print(f"WebSocketClient initialized for agent '{agent_name}' in room '{room_name}' at {server_url}")

    async def connect(self):
        """WebSocketサーバーに接続します。"""
        try:
            full_url = f"{self.server_url}/ws?room={self.room_name}&agent={self.agent_name}"
            self.websocket = await websockets.connect(full_url)
            print(f"Connected to WebSocket: {full_url}")
            self._listener_task = asyncio.create_task(self._listen_for_messages())
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.websocket = None

    async def disconnect(self):
        """WebSocketサーバーから切断します。"""
        if self.websocket:
            await self.websocket.close()
            print("Disconnected from WebSocket.")
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task # タスクの完了を待つ（キャンセル例外を処理）
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        self.websocket = None

    async def send_message(self, message: Dict[str, Any]):
        """WebSocket経由でメッセージを送信します。"""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(message))
                print(f"Sent message via WebSocket: {message}")
            except Exception as e:
                print(f"Failed to send message via WebSocket: {e}")
            except TypeError as e: # シリアライズできないオブジェクトが渡された場合
                print(f"Failed to serialize message for WebSocket: {e} - Message: {message}")
        else:
            print("WebSocket is not connected. Message not sent.")

    async def _listen_for_messages(self):
        """WebSocketからのメッセージをリッスンし、コールバックを非同期タスクとして実行します。"""
        try:
            while True:
                message_str = await self.websocket.recv()
                message_data = json.loads(message_str)
                print(f"Received message via WebSocket: {message_data}")
                # コールバックを待たずに実行することで、リスナーがブロックされるのを防ぐ
                asyncio.create_task(self.on_message(message_data))
        except websockets.exceptions.ConnectionClosedOK:
            print("WebSocket connection closed normally.")
        except Exception as e:
            print(f"WebSocket listener error: {e}")
        finally:
            print("WebSocket listener stopped.")
            self.websocket = None # 接続が切れたらwebsocketをNoneにする
            self._listener_task = None
