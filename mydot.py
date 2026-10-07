import subprocess
import time
import json
import urllib.request

from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent

INBOX = BASE / "inbox"
DONE = BASE / "done"
LOGS = BASE / "logs"

WORKSPACE = BASE / "workspace"

POLL_SECONDS = 3

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:8b"

HISTORY_FILE = BASE / "state" / "conversation.json"
MAX_HISTORY = 20

def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        if isinstance(history, list):
            return history[-MAX_HISTORY:]

    except Exception as e:
        print(f"[MyDot] 履歴読み込みエラー: {e}")

    return []


def save_history():
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    temp_file = HISTORY_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            conversation_history,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp_file.replace(HISTORY_FILE)


conversation_history = load_history()

def classify_task(task: str) -> str:
    prompt = f"""
次の依頼を LOCAL または CODE のどちらか1語だけで分類してください。

CODE:
- ファイルを作成・変更・削除する
- プログラムを書く・修正する
- shellコマンドを実行する
- Git/Docker/systemdなどを操作する

LOCAL:
- 質問への回答
- 説明
- 要約
- 分析
- アイデア出し

依頼:
{task}

回答は LOCAL または CODE の1語だけ。
"""

    data = json.dumps({
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": -1,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

    answer = result["message"]["content"].strip().upper()

    if answer == "CODE":
        return "CODE"

    return "LOCAL"

def run_local(task: str) -> str:
    global conversation_history

    messages = [
        {
            "role": "system",
            "content": (
                "あなたはMyDotというパーソナルAIアシスタントです。"
                "過去の会話を踏まえて自然に回答してください。"
            ),
        }
    ]

    messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": task,
    })

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": -1,
        "messages": messages,
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    answer = result["message"]["content"]

    conversation_history.append({
        "role": "user",
        "content": task,
    })

    conversation_history.append({
        "role": "assistant",
        "content": answer,
    })

    conversation_history = conversation_history[-MAX_HISTORY:]

    save_history()

    return answer

def run_codex(task: str) -> str:
    print(f"[MyDot] Codex起動: {task}")

    result = subprocess.run(
        [
            "codex",
            "exec",
            "--sandbox",
            "workspace-write",
            task,
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
    )

    return (
        f"returncode: {result.returncode}\n\n"
        f"===== STDOUT =====\n{result.stdout}\n"
        f"===== STDERR =====\n{result.stderr}\n"
    )


def process_task(task_file: Path):
    task = task_file.read_text(encoding="utf-8").strip()

    if not task:
        print(f"[MyDot] 空のタスク: {task_file.name}")
        task_file.rename(DONE / task_file.name)
        return

    print(f"[MyDot] タスク検知: {task_file.name}")

    print(f"[MyDot] タスク検知: {task_file.name}")

    route = classify_task(task)
    print(f"[MyDot] ルート判定: {route}")

    if route == "CODE":
        result = run_codex(task)
    else:
        result = run_local(task)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS / f"{timestamp}_{task_file.stem}.log"
    log_file.write_text(result, encoding="utf-8")

    task_file.rename(DONE / task_file.name)

    print(f"[MyDot] 完了: {task_file.name}")
    print(f"[MyDot] ログ: {log_file}")


def main():
    print("[MyDot] 起動")
    print(f"[MyDot] inbox監視中: {INBOX}")

    while True:
        try:
            for task_file in sorted(INBOX.glob("*.txt")):
                process_task(task_file)

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("\n[MyDot] 終了")
            break

        except Exception as e:
            print(f"[MyDot] ERROR: {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
