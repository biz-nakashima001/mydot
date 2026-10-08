import subprocess
import time
import json
import urllib.request
import fcntl
from contextlib import contextmanager

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

MEMORY_FILE = BASE / "state" / "memory.json"

LOCK_FILE = BASE / "state" / "conversation.lock"


@contextmanager
def conversation_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOCK_FILE, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        if isinstance(history, list):
            return history

    except Exception as e:
        print(f"[MyDot] 履歴読み込みエラー: {e}")

    return []

def load_memory():
    if not MEMORY_FILE.exists():
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)

        if isinstance(memory, list):
            return memory

    except Exception as e:
        print(f"[MyDot] 長期記憶読み込みエラー: {e}")

    return []


def save_memory(memory):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    temp_file = MEMORY_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            memory,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp_file.replace(MEMORY_FILE)


long_term_memory = load_memory()


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

def extract_memories(messages: list) -> list:
    """会話から長期保存する価値のある情報を抽出する。"""

    prompt = f"""
あなたはMyDotの長期記憶管理AIです。

以下の会話から、今後の会話で役立つ情報だけを抽出してください。

保存対象:
- ユーザーが明示した継続的な好みや方針
- 進行中のプロジェクトの重要な設定
- 今後も参照する必要がある決定事項

保存しない情報:
- 一時的な雑談や挨拶
- 根拠のない推測
- パスワード、APIキーなどの秘密情報
- 明示的に記憶を求められていない機微な個人情報

重要な情報がなければ空配列にしてください。

JSON形式のみで回答してください。
例:
{{"memories": ["MyDotはローカルLLMを使用する"]}}

会話:
{json.dumps(messages, ensure_ascii=False)}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "keep_alive": -1,
        "think": False,
        "format": "json",
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(
            request, timeout=120
        ) as response:
            result = json.loads(response.read().decode("utf-8"))

        content = result["message"]["content"]

        extracted = json.loads(content)

        if not isinstance(extracted, dict):
            raise ValueError("記憶抽出結果がJSONオブジェクトではありません")

        if "memories" not in extracted:
            raise ValueError("記憶抽出結果にmemoriesキーがありません")

        memories = extracted["memories"]

        if not isinstance(memories, list):
            raise ValueError("memoriesが配列ではありません")

        if not all(isinstance(item, str) for item in memories):
            raise ValueError("memoriesに文字列以外の値が含まれています")

        return [
            item.strip()
            for item in memories
            if isinstance(item, str) and item.strip()
        ]

    except Exception as e:
        print(f"[MyDot] 記憶抽出エラー: {e}")
        raise

def add_memories(memories: list) -> int:
    """新しい長期記憶を追加する。完全一致の重複は除外する。"""
    global long_term_memory

    added = 0

    for item in memories:
        if not isinstance(item, str):
            continue

        item = item.strip()

        if not item:
            continue

        if item not in long_term_memory:
            long_term_memory.append(item)
            added += 1

    if added > 0:
        save_memory(long_term_memory)

    return added


def run_local(task: str) -> str:
    with conversation_lock():
        return _run_local_locked(task)


def _run_local_locked(task: str) -> str:
    global conversation_history, long_term_memory

    # ロック取得後、最新のファイルを読み直す
    conversation_history = load_history()
    long_term_memory = load_memory()
    memory_text = "\n".join(
        f"- {item}" for item in long_term_memory
    )

    system_prompt = """
    あなたはMyDotというパーソナルAIアシスタントです。
    過去の会話を踏まえて自然に回答してください。

    以下は長期記憶です。
    必要な場合のみ回答に利用してください。

    --- 長期記憶 ---
    {memory}
    --- 長期記憶ここまで ---
    """.format(
        memory=memory_text if memory_text else "なし"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
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

    # 短期記憶の上限を超えた場合
    if len(conversation_history) > MAX_HISTORY:

        overflow_count = len(conversation_history) - MAX_HISTORY

        # 古い会話を取り出す
        old_messages = conversation_history[:overflow_count]

        # 先に会話履歴全体を保存し、抽出失敗時の復旧に備える
        save_history()

        try:
            # 古い会話から重要情報を抽出
            new_memories = extract_memories(old_messages)

            # 長期記憶に追加
            added = add_memories(new_memories)

            print(f"[MyDot] 長期記憶を{added}件追加")

            # 正常終了した場合だけ履歴を整理
            conversation_history = conversation_history[-MAX_HISTORY:]

        except Exception as e:
            print(f"[MyDot] 自動記憶エラー: {e}")
            print("[MyDot] 古い会話を保持して次回再試行します")

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
