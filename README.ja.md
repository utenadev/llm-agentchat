# llm-agentchat

[simonw/llm](https://github.com/simonw/llm) のためのプラグインで、複数のLLMエージェントが協働するためのチャット環境を提供します。

---

## 概要

`llm-agentchat` は、`simonw/llm` CLI上で動作する、LLMエージェント協働のためのチャットシステムです。このシステムは、HTTPとWebSocketを介してエージェント間のリアルタイム通信を可能にし、Webブラウザからその対話をモニタリングおよび介入できるユーザーインターフェースを提供します。サーバーとクライアントの分離により、異なるPC間での分散協働もサポートします。

## 主な機能

- **マルチエージェントチャット**: 複数のLLMエージェントが指定されたチャットルームで対話し、協働できます。
- **リアルタイムWeb UI**: ブラウザを通じてエージェントたちの会話をリアルタイムで監視し、人間がチャットに介入できます。
- **柔軟なエージェント設定**: YAMLファイル (`agents.yml`) で、各エージェントのペルソナ、使用モデル、利用可能なツールを簡単に定義できます。
- **`llm`エコシステムとの連携**: `simonw/llm`で設定済みのモデルやAPIキー、`llm-code`のようなツールプラグインをシームレスに利用できます。
- **チャット履歴の永続化**: 会話はSQLiteデータベースに保存され、サーバー再起動後も履歴を確認できます。

## インストール

`uv`コマンド（または`pip`）を使用してインストールします。

```bash
uv pip install llm-agentchat
```
または、このリポジトリをクローンしてインストールすることも可能です。
```bash
git clone https://github.com/utenadev/llm-agentchat.git
cd llm-agentchat
uv pip install -e .
```

## 使い方

### 1. エージェントの定義

まず、プロジェクトのルートに `agents.yml` ファイルを作成し、参加させたいエージェントを定義します。

```yaml
# agents.yml
agents:
  - name: "ProgrammerAgent"
    model: "gemini-1.5-flash"
    persona: |
      あなたは優秀なプログラマーです。
      与えられた課題を解決するPythonコードを作成してください。
    tools:
      - "code" # llm-code プラグインが必要

  - name: "ReviewerAgent"
    model: "gemini-1.5-pro"
    persona: |
      あなたは優秀なコードレビューアです。
      プログラマーAgentが書いたコードをレビューし、
      改善点を提案してください。

common_settings:
  chat_history_limit: 10
  response_delay_ms: 1000
```

### 2. チャットサーバーの起動

ターミナルで以下のコマンドを実行し、チャットサーバーを起動します。

```bash
llm agentchat-server my-chat-room
```

これにより、`http://127.0.0.1:8000` でサーバーが起動し、自動的にブラウザでWeb UIが開きます。

### 3. エージェントの起動

別のターミナルを必要な数だけ開き、各エージェントをチャットルームに参加させます。

```bash
# ProgrammerAgentを参加させる
llm agentchat-client my-chat-room ProgrammerAgent -a agents.yml

# ReviewerAgentを参加させる
llm agentchat-client my-chat-room ReviewerAgent -a agents.yml
```

### 4. チャットへの参加

ブラウザのWeb UIからメッセージを送信することで、人間としてチャットに参加し、エージェントと対話できます。`@AgentName` で特定のエージェントにメンションすることも可能です。

## ライセンス

このプロジェクトは Apache License, Version 2.0 の下で公開されています。
