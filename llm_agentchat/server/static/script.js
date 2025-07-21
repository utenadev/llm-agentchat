document.addEventListener('DOMContentLoaded', async () => {
    const messagesUl = document.getElementById('messages');
    const form = document.getElementById('form');
    const input = document.getElementById('input');

    // 現在のルーム名をURLから取得
    const urlParams = new URLSearchParams(window.location.search);
    const roomName = urlParams.get('room') || 'default_room'; // デフォルトルーム名を設定

    // 過去のメッセージを取得して表示する関数
    async function fetchAndDisplayMessages() {
        try {
            const response = await fetch(`/api/messages?room=${roomName}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const messages = await response.json();
            messagesUl.innerHTML = ''; // 既存のメッセージをクリア
            messages.forEach(msg => {
                displayMessage(msg);
            });
        } catch (error) {
            console.error('Failed to fetch messages:', error);
            const errorItem = document.createElement('li');
            errorItem.textContent = `Error loading past messages: ${error.message}`;
            errorItem.style.color = 'red';
            messagesUl.appendChild(errorItem);
        }
    }

    // メッセージをUIに表示するヘルパー関数
    function displayMessage(msg) {
        const item = document.createElement('li');
        const timestamp = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // メッセージの種類に応じてスタイルを決定
        if (msg.sender === 'human') {
            item.className = 'flex justify-end';
            item.innerHTML = `
                <div class="bg-blue-500 text-white p-3 rounded-lg max-w-lg">
                    <p class="whitespace-pre-wrap">${msg.message}</p>
                    <div class="text-right text-xs text-blue-200 mt-1">${timestamp}</div>
                </div>`;
        } else if (msg.sender === 'System' && msg.type === 'system') {
            // "System"からのシステムメッセージ（接続/切断など）
            item.className = 'flex justify-center'; // 中央揃え
            item.innerHTML = `
                <div class="bg-yellow-100 text-yellow-800 text-sm p-2 rounded-lg max-w-lg text-center">
                    ${msg.message}
                </div>`;
        } else { // エージェントからのメッセージ（チャットと参加/離脱などのシステムメッセージを含む）
            item.className = 'flex justify-start';
            const messageContent = (typeof marked !== 'undefined') ? marked.parse(msg.message) : msg.message;
            item.innerHTML = `
                <div class="bg-gray-200 text-gray-800 p-3 rounded-lg max-w-lg">
                    <div class="font-bold">${msg.sender}</div>
                    <div class="prose prose-sm max-w-none mt-1">${messageContent}</div>
                    <div class="text-right text-xs text-gray-500 mt-1">${timestamp}</div>
                </div>`;
        }
        messagesUl.prepend(item);
    }

    // WebSocket接続
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws?room=${roomName}`;
    let socket;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5; // 再接続試行の最大回数

    function connectWebSocket() {
        socket = new WebSocket(wsUrl);

        socket.onopen = (event) => {
            reconnectAttempts = 0; // 接続成功時にリセット
            console.log('WebSocket connected:', event);
            // 接続成功後に過去のメッセージをロード
            fetchAndDisplayMessages();
            displayMessage({ sender: 'System', message: 'Connected to chat.', timestamp: new Date().toISOString(), type: 'system' });
        };

        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            displayMessage(message);
            messagesUl.scrollTop = 0; // 新しいメッセージ表示後に一番上までスクロール
        };

        socket.onclose = (event) => {
            console.log('WebSocket disconnected:', event);
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                displayMessage({ sender: 'System', message: `Disconnected from chat. Reconnecting... (Attempt ${reconnectAttempts}/${maxReconnectAttempts})`, timestamp: new Date().toISOString(), type: 'system' });
                setTimeout(connectWebSocket, 3000); // 3秒後に再接続を試みる
            } else {
                displayMessage({ sender: 'System', message: 'Could not reconnect to the server. Please refresh the page.', timestamp: new Date().toISOString(), type: 'system' });
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            // styleプロパティを削除
            displayMessage({ sender: 'System', message: `WebSocket error: ${error.message}`, timestamp: new Date().toISOString(), type: 'system' });
            socket.close(); // エラー時は接続を閉じて再接続を試みる
        };
    }

    // Ctrl+Enterで送信するためのイベントリスナー
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault(); // 本来の改行動作をキャンセル
            form.requestSubmit(); // フォームの送信イベントを発火
        }
    });

    // フォーム送信ハンドラ
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (input.value) {
            const messageText = input.value;
            const message = {
                room: roomName,
                sender: 'human', // 人間からのメッセージ
                message: messageText,
                type: 'chat'
            };

            try {
                // HTTP POSTでメッセージを送信
                const response = await fetch('/api/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(message)
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const result = await response.json();
                console.log('Message sent:', result);
                input.value = ''; // 入力フィールドをクリア

            } catch (error) {
                console.error('Failed to send message:', error);
                displayMessage({ sender: 'System', message: `Error sending message: ${error.message}`, timestamp: new Date().toISOString(), type: 'system', style: 'color: red;' });
            }
        }
    });

    // アプリケーション開始
    connectWebSocket();
});
