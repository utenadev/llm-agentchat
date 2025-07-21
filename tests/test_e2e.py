import pytest
import asyncio
import httpx
import websockets
import json
from multiprocessing import Process
import uvicorn
import time
from contextlib import closing
import socket
import os

# NOTE: このテストファイルは、実際のサーバーをバックグラウンドで起動してE2Eテストを行います。
# `fastapi`, `uvicorn`, `httpx`, `websockets` がインストールされている必要があります。
try:
    from llm_agentchat.server.app import app
    _server_module_found = True
except (ImportError, ModuleNotFoundError):
    _server_module_found = False
    app = None

def find_free_port():
    """利用可能なポートを動的に見つけます。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def run_server(host, port):
    """uvicornサーバーを実行するターゲット関数。"""
    # E2Eテスト用にファイルベースのDBパスをハードコーディング
    app.state.db_path = "test_e2e_chat_history.db"
    uvicorn.run(app, host=host, port=port, log_level="info")

@pytest.fixture(scope="module")
def live_server():
    """テスト用にバックグラウンドでFastAPIサーバーを起動するフィクスチャ。"""
    if not _server_module_found:
        pytest.skip("server module `llm_agentchat.server.app` not found")

    host = "127.0.0.1"
    port = find_free_port()
    
    proc = Process(target=run_server, args=(host, port), daemon=True)
    proc.start()
    
    # サーバーが起動するのを待ちます (ポーリングによる確認)
    server_url = f"http://{host}:{port}"
    for _ in range(20): # 最大2秒間ポーリング (0.1秒 * 20回)
        try:
            with httpx.Client() as client:
                response = client.get(server_url, timeout=0.1)
                if response.status_code == 200:
                    break
        except httpx.RequestError:
            pass # 接続エラーは無視してリトライ
        time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail(f"Server failed to start at {server_url} within timeout.")

    yield f"http://{host}:{port}"
    
    proc.terminate()
    # テスト後にデータベースファイルをクリーンアップ
    if os.path.exists("test_e2e_chat_history.db"):
        os.remove("test_e2e_chat_history.db")


@pytest.mark.skipif(not _server_module_found, reason="server module `llm_agentchat.server.app` not found")
@pytest.mark.asyncio # async テストを認識させるために必要
async def test_e2e_human_sends_message_and_client_receives_it(live_server):
    """
    E2Eテスト: 人間がHTTP経由でメッセージを送信し、WebSocketクライアントがそれを受信することを確認します。
    """
    room_name = "e2e-test-room"
    http_url = f"{live_server}/api/message"
    ws_url = f"{live_server.replace('http', 'ws')}/ws?room={room_name}&agent=test-ws-client"

    message_received = asyncio.Future()

    async def ws_client():
        try:
            async with websockets.connect(ws_url, open_timeout=10) as websocket:
                message_str = await asyncio.wait_for(websocket.recv(), timeout=10)
                message_received.set_result(json.loads(message_str))
        except Exception as e:
            if not message_received.done():
                message_received.set_exception(e)

    client_task = asyncio.create_task(ws_client())
    await asyncio.sleep(1) # クライアントの接続を待つ

    async with httpx.AsyncClient() as client:
        post_data = {
            "room": room_name, "sender": "human", "message": "Hello from E2E test", "type": "chat"
        }
        response = await client.post(http_url, json=post_data)
        assert response.status_code == 200

    try:
        received_message = await asyncio.wait_for(message_received, timeout=5)
    finally:
        client_task.cancel()

    assert received_message["message"] == "Hello from E2E test"
    assert received_message["sender"] == "human"
    assert received_message["room"] == room_name
