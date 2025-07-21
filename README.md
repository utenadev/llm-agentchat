# llm-agentchat

A plugin for [simonw/llm](https://github.com/simonw/llm) that provides a chat environment for multiple LLM agents to collaborate.

---

## Overview

`llm-agentchat` is a chat system for LLM agent collaboration that runs on the `simonw/llm` CLI. This system enables real-time communication between agents via HTTP and WebSocket, and provides a user interface to monitor and intervene in their conversations from a web browser. The separation of server and client also supports distributed collaboration across different PCs.

## Key Features

- **Multi-Agent Chat**: Multiple LLM agents can converse and collaborate in a designated chat room.
- **Real-time Web UI**: Monitor the agents' conversations in real-time and intervene in the chat as a human through the browser.
- **Flexible Agent Configuration**: Easily define each agent's persona, model, and available tools in a YAML file (`agents.yml`).
- **Integration with `llm` Ecosystem**: Seamlessly use models and API keys configured in `simonw/llm`, as well as tool plugins like `llm-code`.
- **Persistent Chat History**: Conversations are saved to an SQLite database, allowing you to review the history even after a server restart.

## Installation

Install using the `uv` command (or `pip`).

```bash
uv pip install llm-agentchat
```
Alternatively, you can clone this repository and install it.
```bash
git clone https://github.com/your-repo/llm-agentchat.git
cd llm-agentchat
uv pip install -e .
```

## Usage

### 1. Define Agents

First, create an `agents.yml` file in the project root and define the agents you want to participate.

```yaml
# agents.yml
agents:
  - name: "ProgrammerAgent"
    model: "gemini-1.5-flash"
    persona: |
      You are an excellent programmer.
      Create Python code to solve the given tasks.
    tools:
      - "code" # Requires the llm-code plugin

  - name: "ReviewerAgent"
    model: "gemini-1.5-pro"
    persona: |
      You are an excellent code reviewer.
      Review the code written by the ProgrammerAgent and
      suggest improvements.

common_settings:
  chat_history_limit: 10
  response_delay_ms: 1000
```

### 2. Start the Chat Server

Run the following command in a terminal to start the chat server.

```bash
llm agentchat-server my-chat-room
```

This will start the server at `http://127.0.0.1:8000` and automatically open the Web UI in your browser.

### 3. Start the Agents

Open as many new terminals as you need and have each agent join the chat room.

```bash
# Have ProgrammerAgent join
llm agentchat-client my-chat-room ProgrammerAgent -a agents.yml

# Have ReviewerAgent join
llm agentchat-client my-chat-room ReviewerAgent -a agents.yml
```

### 4. Join the Chat

You can join the chat as a human by sending messages from the Web UI to interact with the agents. You can also mention a specific agent with `@AgentName`.

## License

This project is licensed under the Apache License, Version 2.0.
