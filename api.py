from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from mydot import classify_task, run_local, run_codex

app = FastAPI(title="MyDot API")


class AskRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
def root():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyDot</title>

    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }

        h1 {
            text-align: center;
        }

        #chat {
            background: white;
            border-radius: 12px;
            padding: 20px;
            min-height: 400px;
            margin-bottom: 15px;
        }

        .message {
            margin: 12px 0;
            white-space: pre-wrap;
        }

        .user {
            font-weight: bold;
        }

        .mydot {
            color: #333;
        }

        .route {
            font-size: 12px;
            color: #888;
        }

        #input-area {
            display: flex;
            gap: 10px;
        }

        #message {
            flex: 1;
            padding: 12px;
            font-size: 16px;
        }

        button {
            padding: 12px 20px;
            font-size: 16px;
            cursor: pointer;
        }
    </style>
</head>

<body>

<h1>MyDot</h1>

<div id="chat"></div>

<div id="input-area">
    <input
        id="message"
        type="text"
        placeholder="MyDotに話しかける..."
        autofocus
    >
    <button onclick="sendMessage()">送信</button>
</div>

<script>
async function sendMessage() {

    const input = document.getElementById("message");
    const chat = document.getElementById("chat");

    const message = input.value.trim();

    if (!message) {
        return;
    }

    chat.innerHTML +=
        '<div class="message user">You: ' +
        escapeHtml(message) +
        '</div>';

    input.value = "";

    const waiting = document.createElement("div");
    waiting.className = "message mydot";
    waiting.textContent = "MyDot: 考え中...";
    chat.appendChild(waiting);

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        waiting.innerHTML =
            '<span class="route">[' +
            escapeHtml(data.route) +
            ']</span><br>' +
            'MyDot: ' +
            escapeHtml(data.answer);

    } catch (error) {

        waiting.textContent =
            "MyDot: エラーが発生しました。";

    }

    chat.scrollTop = chat.scrollHeight;
}


function escapeHtml(text) {

    const div = document.createElement("div");
    div.textContent = text;

    return div.innerHTML;
}


document.getElementById("message")
    .addEventListener("keydown", function(event) {

        if (event.key === "Enter") {
            sendMessage();
        }

    });
</script>

</body>
</html>
"""

@app.post("/ask")
def ask(request: AskRequest):
    task = request.message.strip()

    route = classify_task(task)

    if route == "CODE":
        answer = run_codex(task)
    else:
        answer = run_local(task)

    return {
        "route": route,
        "answer": answer,
    }
