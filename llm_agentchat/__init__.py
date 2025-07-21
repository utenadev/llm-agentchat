import llm
import click
import uvicorn
import webbrowser
import os
from llm_agentchat.server.app import app # FastAPIアプリケーションをインポート

@llm.hookimpl
def register_commands(cli: click.Group) -> None:
    """
    llm-agentchat の CLI コマンドを登録します。
    """

    @cli.command(name="agentchat-server")
    @click.argument("room_name")
    @click.option(
        "-p",
        "--port",
        default=8000,
        type=int,
        help="サーバーがリッスンするポート番号 (デフォルト: 8000)",
    )
    @click.option(
        "--host",
        default="127.0.0.1",
        help="サーバーがリッスンするホスト (デフォルト: 127.0.0.1)",
    )
    @click.option(
        "-s",
        "--storage",
        default="chat_history.db",
        help="チャット履歴を保存するSQLiteデータベースファイルのパス (デフォルト: chat_history.db)",
    )
    @click.option(
        "--no-browser",
        is_flag=True,
        help="サーバー起動後にWeb UIを自動的に開かない",
    )
    def server(room_name: str, port: int, host: str, storage: str, no_browser: bool) -> None:
        """
        エージェントチャットサーバーを起動します。
        """
        click.echo(f"Starting agentchat server for room: {room_name}")
        
        # データベースパスをアプリケーションの状態に設定
        app.state.db_path = storage

        # FastAPIアプリケーションをUvicornで起動
        click.echo(f"Server starting on http://{host}:{port}")
        if not no_browser:
            try:
                # ブラウザを開く前にサーバーが起動するのを少し待つ
                webbrowser.open_new_tab(f"http://{host}:{port}?room={room_name}")
            except Exception as e:
                click.echo(f"Warning: Could not open browser automatically: {e}", err=True)

        uvicorn.run(app, host=host, port=port, log_level="info")

    import asyncio
    import yaml
    from llm_agentchat.client.agent import Agent # Agentクラスをインポート
    from llm_agentchat.client.websocket_client import WebSocketClient # WebSocketClientをインポート

    @cli.command(name="agentchat-client")
    @click.argument("room_name")
    @click.argument("agent_name")
    @click.option(
        "-u",
        "--server-url",
        default="ws://127.0.0.1:8000",
        help="WebSocketサーバーのURL (デフォルト: ws://127.0.0.1:8000)",
    )
    @click.option(
        "-a",
        "--agents-file",
        default="agents.yml",
        type=click.Path(exists=True),
        help="エージェント定義ファイルのパス (デフォルト: agents.yml)",
    )
    def client(room_name: str, agent_name: str, server_url: str, agents_file: str) -> None:
        """
        エージェントをチャットルームに参加させます。
        """
        click.echo(
            f"Starting agentchat client for agent '{agent_name}' in room: {room_name}"
        )
        click.echo(f"Connecting to server: {server_url}")

        # エージェント設定のロード
        try:
            with open(agents_file, 'r', encoding='utf-8') as f:
                agents_config = yaml.safe_load(f)
        except Exception as e:
            click.echo(f"Error loading agents file: {e}", err=True)
            return

        agent_config = next((a for a in agents_config.get('agents', []) if a['name'] == agent_name), None)
        if not agent_config:
            click.echo(f"Error: Agent '{agent_name}' not found in '{agents_file}'", err=True)
            return

        common_settings = agents_config.get('common_settings', {})

        # エージェントインスタンスの作成
        # on_message_received と on_send_message コールバックを渡すための準備
        # これらは後で WebSocketClient と Agent 間で接続されます
        agent = Agent(
            config=agent_config,
            room_name=room_name,
            server_url=server_url,
            common_settings=common_settings,
        )

        # WebSocketClientインスタンスを作成し、エージェントの受信ハンドラを登録
        ws_client = WebSocketClient(
            server_url=server_url,
            room_name=room_name,
            agent_name=agent_name,
            on_message=agent.handle_message_from_server # エージェントのメソッドを受信ハンドラとして渡す
        )
            
        # エージェントがメッセージを送信する際にws_clientを使うように設定
        agent.set_websocket_client(ws_client)

        async def main_client_loop():
            await ws_client.connect()
            if ws_client.websocket:
                # エージェントの起動ロジック
                # 例: 接続成功メッセージを送信、LLMによる初回発言など
                initial_message = {
                    "room": room_name,
                    "sender": agent_name,
                    "message": f"Hello, I am {agent_name} and I have joined the chat!",
                    "type": "system"
                }
                await ws_client.send_message(initial_message)
                    
                # エージェントのメインループを開始（永続的にメッセージを処理）
                await agent.start_listening() # このメソッドは無限ループを想定

            else:
                click.echo("Failed to establish WebSocket connection.", err=True)

        asyncio.run(main_client_loop())
