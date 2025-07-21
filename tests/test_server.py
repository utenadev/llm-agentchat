import pytest
from unittest.mock import patch

# NOTE: このテストファイルは、プロジェクトの設計ドキュメントに基づいたスケルトンです。
# `fastapi`と`llm_agentchat.server.app`モジュールが実装されている必要があります。
try:
    from fastapi.testclient import TestClient
    from llm_agentchat.server.app import app
    _fastapi_installed = True
except (ImportError, ModuleNotFoundError):
    _fastapi_installed = False
    # モジュールが存在しない場合、テストをスキップするために変数を定義します。
    TestClient = None
    app = None

@pytest.mark.skipif(not _fastapi_installed, reason="fastapi or llm_agentchat.server.app not found")
class TestServerAPI:
    """サーバーのAPIエンドポイントをテストするクラス。"""

    def setup_method(self):
        """各テストの前にクライアントをセットアップします。"""
        # テスト用にインメモリデータベースを使用
        app.state.db_path = ":memory:"
        self.client = TestClient(app)

    @patch('llm_agentchat.server.app.db')
    def test_get_messages(self, mock_db):
        """
        GET /api/messages エンドポイントをテストします。
        指定されたルームのメッセージが正しく返されることを確認します。
        """
        # データベースモックのセットアップ
        mock_conn = mock_db.get_db.return_value
        mock_db.get_messages_for_room.return_value = [
            {'sender': 'agent1', 'message_content': 'Hello'},
            {'sender': 'agent2', 'message_content': 'Hi'}
        ]

        response = self.client.get("/api/messages?room=test-room")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]['sender'] == 'agent1'
        mock_db.get_messages_for_room.assert_called_once_with(mock_conn, 'test-room')

    @patch('llm_agentchat.server.app.broadcast_message')
    @patch('llm_agentchat.server.app.db')
    def test_post_message(self, mock_db, mock_broadcast):
        """
        POST /api/message エンドポイントをテストします。
        メッセージが正常に投稿され、ブロードキャストされることを確認します。
        """
        message_data = {
            "room": "test-room",
            "sender": "human",
            "message": "This is a test",
            "type": "chat"
        }
        
        response = self.client.post("/api/message", json=message_data)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_db.add_message.assert_called_once()
        mock_broadcast.assert_called_once()

    def test_get_agents_endpoint(self):
        """
        GET /api/agents エンドポイントをテストします。
        WebSocketで接続中のエージェントリストが正しく返されることを確認します。
        """
        room_name = "live-test-room"

        # エージェントがいない状態でAPIを叩く
        response = self.client.get(f"/api/agents?room={room_name}")
        assert response.status_code == 200
        assert response.json() == []

        # agent1が接続
        with self.client.websocket_connect(f"/ws?room={room_name}&agent=agent1") as websocket1:
            response = self.client.get(f"/api/agents?room={room_name}")
            assert response.status_code == 200
            assert response.json() == ["agent1"]

            # agent2が接続
            with self.client.websocket_connect(f"/ws?room={room_name}&agent=agent2") as websocket2:
                response = self.client.get(f"/api/agents?room={room_name}")
                assert response.status_code == 200
                # 順序は不定なので、集合で比較
                assert set(response.json()) == {"agent1", "agent2"}
            
            # agent2が切断された後
            response = self.client.get(f"/api/agents?room={room_name}")
            assert response.status_code == 200
            assert response.json() == ["agent1"]

        # 全員が切断された後
        response = self.client.get(f"/api/agents?room={room_name}")
        assert response.status_code == 200
        assert response.json() == []
