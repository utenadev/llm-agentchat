import llm # simonw/llm ライブラリのllmオブジェクトをインポート
import asyncio
from typing import Dict, Any, List, Optional
import httpx # HTTP通信用
import yaml # エージェント設定ファイル読み込み用
import os # ファイルパス操作用

class Agent:
    """
    LLMエージェントのコアロジックを管理するクラス。
    """
    def __init__(self, config: Dict[str, Any], room_name: str, server_url: str, common_settings: Dict[str, Any]):
        """
        エージェントを初期化します。
        """
        self.name = config["name"]
        self.model = config["model"]
        self.persona = config["persona"]
        self.options = config.get("options", {}) # モデル固有のオプション
        self.room_name = room_name
        self.server_url = server_url.replace("ws://", "http://").replace("wss://", "https://") # HTTP API用
        self.websocket_client: Optional[Any] = None # WebSocketClientインスタンスを保持
        self.chat_history: List[Dict[str, str]] = [] # 会話履歴を保持
        self._is_listening = asyncio.Event() # メッセージリスニング状態を制御
        
        # 共通設定を適用
        self.chat_history_limit = common_settings.get('chat_history_limit', 10)
        self.response_delay_ms = common_settings.get('response_delay_ms', 0)
        
        print(f"Agent '{self.name}' initialized. History limit: {self.chat_history_limit}, Delay: {self.response_delay_ms}ms")

    def set_websocket_client(self, ws_client: Any):
        """WebSocketClientインスタンスを設定します。"""
        self.websocket_client = ws_client

    async def _send_message(self, message_content: str, message_type: str = "chat"):
        """メッセージをサーバーに送信します（WebSocket経由）。"""
        message_data = {
            "room": self.room_name,
            "sender": self.name,
            "message": message_content,
            "type": message_type
        }
        if self.websocket_client:
            await self.websocket_client.send_message(message_data)
        else:
            print("Error: WebSocket client not set for Agent.")

    async def _generate_response(self) -> str:
        """
        LLMを使用して応答を生成します。レートリミットなどのエラーに対応するためリトライロジックを含みます。
        """
        print(f"Agent '{self.name}' generating response...")
        # 会話履歴をLLMに渡す前に制限を適用
        history_to_send = self.chat_history[-self.chat_history_limit:]

        # llmライブラリが期待する辞書のリストを作成
        # personaがYAMLファイルでリスト（ネストされている可能性も含む）として定義されている場合に対処
        if isinstance(self.persona, list):
            # 全ての要素（リストを含む）を強制的に文字列に変換してから結合する
            persona_content = "\n".join(map(str, self.persona))
        else:
            persona_content = str(self.persona)
        
        # messagesリストには会話履歴のみを含める
        messages = []
        for msg in history_to_send:
            # メッセージの "sender" を "role" にマッピング
            # 自分の発言は "assistant", それ以外 (human, 他のエージェント) は "user" とする
            role = "user"
            if msg.get("sender") == self.name:
                role = "assistant"
            
            # システムメッセージはLLMへのコンテキストに含めない
            if msg.get("type") != "system":
                 messages.append({"role": role, "content": msg.get("message", "")})

        # llmライブラリの会話形式の不具合を回避するため、
        # 会話履歴を手動で1つの文字列にフォーマットする
        conversation_str = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation_str += f"{role}: {content}\n\n"

        # llmライブラリを使用してモデルからの応答を得る
        model = llm.get_model(self.model)
        
        max_retries = 3
        backoff_factor = 2  # seconds

        for attempt in range(max_retries):
            try:
                # model.promptは同期的なブロッキング呼び出しのため、asyncio.to_threadを使用して
                # イベントループをブロックしないように別スレッドで実行します。
                response = await asyncio.to_thread(
                    model.prompt, conversation_str.strip(), system=persona_content, **self.options
                )
                
                text_response = response.text()
                
                # 応答がリストであるかチェック
                if isinstance(text_response, list):
                    if not text_response:
                        return ""
                    final_text = text_response[0]
                    while isinstance(final_text, list) and final_text:
                        final_text = final_text[0]
                    return str(final_text)
                
                return str(text_response)

            except Exception as e:
                print(f"Error generating LLM response (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt + 1 == max_retries:
                    return f"Error: LLM failed to generate a response after {max_retries} attempts."
                
                sleep_time = backoff_factor * (2 ** attempt)
                print(f"Retrying in {sleep_time} seconds...")
                await asyncio.sleep(sleep_time)

        return "Error: LLM failed to generate a response." # Fallback

    async def handle_message_from_server(self, message: Dict[str, Any]):
        """
        サーバーから受信したメッセージを処理します。
        このメソッドがWebSocketClientのコールバックとして登録されます。
        """
        sender = message.get("sender")
        message_content = message.get("message")
        room = message.get("room")
        message_type = message.get("type", "chat")

        # 自身のメッセージは処理しない、または特定のタイプのみ処理
        if sender == self.name:
            return

        if room != self.room_name:
            return # 自身のルーム宛てではないメッセージは無視

        print(f"Agent '{self.name}' received: <{sender}> {message_content}")
        
        # 会話履歴に追加
        self.chat_history.append({"sender": sender, "message": message_content, "type": message_type})

        # LLMに問い合わせて応答を生成
        # プログラマーAgentにメンションされたら応答、または他のエージェントが話したら応答
        if "@" + self.name in message_content or message_type == "chat": # 仮の応答トリガー
            # 応答遅延を適用
            if self.response_delay_ms > 0:
                await asyncio.sleep(self.response_delay_ms / 1000)

            response_text = await self._generate_response()
            await self._send_message(response_text)
            # 自身の応答も履歴に追加
            self.chat_history.append({"sender": self.name, "message": response_text, "type": "chat"})

    async def start_listening(self):
        """
        エージェントがメッセージの受信と処理を開始するメインループ。
        基本的にWebSocketクライアントのリスナーが動いている間は待機する。
        """
        print(f"Agent '{self.name}' is now listening for messages in room '{self.room_name}'.")
        self._is_listening.set() # リスニング状態をTrueに設定
        while self._is_listening.is_set():
            await asyncio.sleep(1) # 無限ループでブロックしないように短時間スリープ
        print(f"Agent '{self.name}' stopped listening.")
