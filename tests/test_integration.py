import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import json
import asyncio

try:
    from llm_agentchat.server.app import app, active_connections
    _server_app_found = True
except (ImportError, ModuleNotFoundError):
    _server_app_found = False
    app = None
    active_connections = {}

@pytest.mark.skipif(not _server_app_found, reason="llm_agentchat.server.app not found")
class TestServerClientIntegration:
    """サーバーとクライアント（WebSocket接続）間の統合をテストするクラス。"""

    client: TestClient # Type hint for the TestClient instance

    def setup_method(self):
        """各テストの前にTestClientをセットアップし、WebSocket接続をクリアします。"""
        # テスト用にインメモリデータベースを使用
        app.state.db_path = ":memory:"
        self.client = TestClient(app)
        # テスト実行前に active_connections をクリア
        active_connections.clear()

    @pytest.mark.asyncio # async テストを認識させるために必要
    @patch('llm_agentchat.server.app.db')
    async def test_http_post_message_broadcasts_to_websocket(self, mock_db):
        """
        HTTP POSTでメッセージが投稿されたときに、接続済みのWebSocketクライアントに
        正しくブロードキャストされることをテストします。
        """
        room_name = "test-integration-room"
        test_message_content = "Hello from integration test!"
        sender_name = "human_user"

        # データベースモックのセットアップ
        # add_message と get_messages_for_room は呼ばれるが、ここでは詳細な動作は不要
        mock_db.add_message.return_value = None
        from unittest.mock import MagicMock # AsyncMockではなくMagicMockをインポート
        mock_db.get_db.return_value = MagicMock() # get_dbもモックしておく

        # WebSocketクライアントを接続
        with self.client.websocket_connect(f"/ws?room={room_name}") as websocket:
            # WebSocket接続が確立されたことを確認 (active_connectionsに登録されているか)
            await asyncio.sleep(0.1) # WebSocket接続処理を待つための少し長めの遅延
            assert room_name in active_connections
            # WebSocketTestSessionは内部接続オブジェクトを直接公開しないため、接続数を検証
            assert len(active_connections[room_name]) == 1

            # HTTP POSTでメッセージを送信
            message_data = {
                "room": room_name,
                "sender": sender_name,
                "message": test_message_content,
                "type": "chat"
            }
            response = self.client.post("/api/message", json=message_data)
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # WebSocketクライアントがメッセージを受信したことを確認
            # TestClientのreceive_text()は同期的に結果を返す
            received_message_str = websocket.receive_text()
            received_message = json.loads(received_message_str)

            assert received_message["room"] == room_name
            assert received_message["sender"] == sender_name
            assert received_message["message"] == test_message_content
            assert "timestamp" in received_message
            assert received_message["type"] == "chat"

            # データベースへの保存が呼ばれたことを確認
            mock_db.add_message.assert_called_once()
            # 引数は位置引数で渡されるため、call_args.argsから取得
            call_args = mock_db.add_message.call_args.args
            assert call_args[1] == room_name  # room_nameは2番目の位置引数
            assert call_args[2] == sender_name # senderは3番目の位置引数
            assert call_args[3] == test_message_content # messageは4番目の位置引数
            assert call_args[4] == "chat" # message_typeは5番目の位置引数

    @pytest.mark.asyncio # async テストを認識させるために必要
    @patch('llm_agentchat.server.app.db')
    async def test_websocket_client_sends_message_and_broadcasts_to_others(self, mock_db):
        """
        WebSocketクライアントがメッセージを送信したときに、他の接続済みクライアントに
        正しくブロードキャストされることをテストします。
        """
        room_name = "test-ws-broadcast-room"
        test_message_content = "Message from WS client!"
        sender_name = "ws_agent"

        from unittest.mock import MagicMock # AsyncMockではなくMagicMockをインポート
        mock_db.add_message.return_value = None
        mock_db.get_db.return_value = MagicMock()

        with self.client.websocket_connect(f"/ws?room={room_name}&agent=ws_sender") as ws_sender:
            with self.client.websocket_connect(f"/ws?room={room_name}&agent=ws_receiver") as ws_receiver:
                await asyncio.sleep(0.1) # WebSocket接続処理を待つための少し長めの遅延
                assert len(active_connections[room_name]) == 2

                # 送信側WebSocketクライアントからメッセージを送信
                message_to_send = {
                    "room": room_name,
                    "sender": sender_name,
                    "message": test_message_content,
                    "type": "chat"
                }
                # TestClientのsend_json()は同期的に動作する
                ws_sender.send_json(message_to_send)

                # 受信側WebSocketクライアントがメッセージを受信したことを確認
                # TestClientのreceive_text()は同期的に結果を返す
                received_message_str = ws_receiver.receive_text()
                received_message = json.loads(received_message_str)

                assert received_message["room"] == room_name
                assert received_message["sender"] == sender_name
                assert received_message["message"] == test_message_content
                assert "timestamp" in received_message
                assert received_message["type"] == "chat"

                # データベースへの保存が呼ばれたことを確認（WebSocketからのメッセージも保存されるようになったため）
                mock_db.add_message.assert_called_once()
                # 引数の検証（タイムスタンプは動的に生成されるため、他の項目を確認）
                call_args = mock_db.add_message.call_args.args
                assert call_args[1] == room_name
                assert call_args[2] == sender_name
                assert call_args[3] == test_message_content
                assert call_args[4] == "chat"
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

# NOTE: このテストファイルは、プロジェクトの設計ドキュメントに基づいたスケルトンです。
# `llm_agentchat.client.agent`モジュールが実装されている必要があります。
try:
    from llm_agentchat.client.agent import Agent
    _agent_module_found = True
except (ImportError, ModuleNotFoundError):
    _agent_module_found = False
    Agent = None

@pytest.fixture
def agent_config():
    """テスト用のエージェント設定を提供するフィクスチャ。"""
    return {
        "name": "TestAgent",
        "model": "gpt-3.5-turbo",
        "persona": "You are a test assistant.",
    }

@pytest.mark.skipif(not _agent_module_found, reason="llm_agentchat.client.agent module not found")
@pytest.mark.asyncio
@patch('llm_agentchat.client.agent.llm')
async def test_agent_response_generation(mock_llm, agent_config):
    """エージェントの応答生成ロジックをモックされたLLMでテストします。"""
    # LLMモックのセットアップ
    mock_model = MagicMock()  # promptは同期的メソッドなのでMagicMockを使用
    mock_response = MagicMock()
    mock_response.text.return_value = "This is a mocked LLM response."
    mock_model.prompt.return_value = mock_response  # promptメソッドがmock_responseを返すように設定
    mock_llm.get_model.return_value = mock_model

    # オプションを持つエージェント設定
    agent_config_with_options = agent_config.copy()
    agent_config_with_options["options"] = {"google_search": 1}

    agent = Agent(config=agent_config_with_options, room_name="test_room", server_url="ws://localhost:8000", common_settings={})
    # 内部状態をセットアップ
    agent.chat_history = [{"sender": "human", "message": "What is pytest?"}]

    # 応答生成メソッド（存在すると仮定）を呼び出します
    response_text = await agent._generate_response()

    mock_llm.get_model.assert_called_with("gpt-3.5-turbo")
    # promptが正しい引数で呼ばれたことを確認
    mock_model.prompt.assert_called_once()
    call_args, call_kwargs = mock_model.prompt.call_args
    assert "system" in call_kwargs
    assert call_kwargs.get("google_search") == 1
    assert response_text == "This is a mocked LLM response."
