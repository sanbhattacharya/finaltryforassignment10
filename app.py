import json
import os
import time
from datetime import datetime
from uuid import uuid4

import requests
import streamlit as st


HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_NAME = "meta-llama/Llama-3.2-1B-Instruct"
CHATS_DIR = "chats"
MEMORY_FILE = "memory.json"


def ensure_chats_dir():
    os.makedirs(CHATS_DIR, exist_ok=True)


def persist_chat(chat: dict[str, str]):
    ensure_chats_dir()
    path = os.path.join(CHATS_DIR, f"{chat['id']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(chat, handle, ensure_ascii=False, indent=2)


def load_chats_from_disk() -> list[dict[str, str]]:
    ensure_chats_dir()
    chats = []
    for filename in sorted(os.listdir(CHATS_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(CHATS_DIR, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                chat = json.load(handle)
        except json.JSONDecodeError:
            continue
        if "history" not in chat:
            chat["history"] = []
        chats.append(chat)
    return chats


def create_chat_entry(existing_count: int) -> dict[str, str]:
    return {
        "id": str(uuid4()),
        "title": f"Chat {existing_count + 1}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history": [],
    }


def ensure_chat_state():
    st.session_state.setdefault("chats", [])
    st.session_state.setdefault("active_chat_id", None)
    st.session_state.setdefault("chats_loaded", False)
    if not st.session_state.chats_loaded:
        loaded = load_chats_from_disk()
        if loaded:
            st.session_state.chats = loaded
        st.session_state.chats_loaded = True
    if not st.session_state.chats:
        st.session_state.chats.append(create_chat_entry(0))
        st.session_state.active_chat_id = st.session_state.chats[0]["id"]
    elif (
        st.session_state.active_chat_id
        not in {chat["id"] for chat in st.session_state.chats}
    ):
        st.session_state.active_chat_id = st.session_state.chats[0]["id"]


def add_new_chat():
    new_chat = create_chat_entry(len(st.session_state.chats))
    st.session_state.chats.append(new_chat)
    st.session_state.active_chat_id = new_chat["id"]
    persist_chat(new_chat)


def delete_chat(chat_id: str):
    st.session_state.chats = [
        chat for chat in st.session_state.chats if chat["id"] != chat_id
    ]
    path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        os.remove(path)
    if st.session_state.active_chat_id == chat_id:
        if st.session_state.chats:
            st.session_state.active_chat_id = st.session_state.chats[0]["id"]
        else:
            st.session_state.active_chat_id = None


def get_active_chat() -> dict[str, str] | None:
    for chat in st.session_state.chats:
        if chat["id"] == st.session_state.active_chat_id:
            return chat
    return None


def render_history(history: list[dict[str, str]]):
    if not history:
        st.info("Send a message to begin the conversation.")
        return

    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def load_memory() -> dict[str, str]:
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, encoding="utf-8") as handle:
            memory = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(memory, dict):
        return {}
    return {str(k): str(v) for k, v in memory.items()}


def save_memory(memory: dict[str, str]):
    if not memory:
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)
        return
    with open(MEMORY_FILE, "w", encoding="utf-8") as handle:
        json.dump(memory, handle, ensure_ascii=False, indent=2)


def reset_memory():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    st.session_state.memory = {}


def update_memory_from_extraction(extracted: dict[str, str]) -> bool:
    cleaned = {str(k): str(v) for k, v in extracted.items() if v is not None and v != ""}
    if not cleaned:
        return False
    st.session_state.memory.update(cleaned)
    save_memory(st.session_state.memory)
    return True


def build_system_message(memory: dict[str, str]) -> dict[str, str]:
    base = (
        "You are a helpful assistant that tries to personalize responses "
        "based on the user’s stored preferences."
    )
    if not memory:
        return {"role": "system", "content": base}
    prefs = "\n".join(f"- {key}: {value}" for key, value in memory.items())
    return {
        "role": "system",
        "content": f"{base}\nRemember these preferences:\n{prefs}",
    }


def stream_hf_chat(history: list[dict[str, str]], memory: dict[str, str], token: str):
    """Stream the response from Hugging Face as SSE chunks."""
    system_message = build_system_message(memory)
    payload = {
        "model": MODEL_NAME,
        "messages": [system_message] + history,
        "max_tokens": 512,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
            stream=True,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed: {exc}")

    if response.status_code != 200:
        raise RuntimeError(
            f"Hugging Face router returned {response.status_code}: {response.text}"
        )

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped.split("data:", 1)[1].strip()
        if payload == "[DONE]":
            break
        event = json.loads(payload)
        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta")
        if delta and "content" in delta:
            chunk = delta["content"]
            yield chunk
            time.sleep(0.05)


def extract_memory_from_message(user_message: str, token: str) -> dict[str, str]:
    prompt = (
        "You are helping the assistant remember user preferences. "
        "When given a user message, return a JSON object with any personal traits, "
        "preferences, or facts mentioned (name, topics, interests, communication style, etc.). "
        "If nothing is present, return {}. Only output JSON."
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.0,
        "max_tokens": 128,
    }

    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Memory extraction failed: {exc}")

    if response.status_code != 200:
        raise RuntimeError(
            f"Memory extraction failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if not content:
        return {}
    try:
        extracted = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Memory extraction response invalid JSON: {exc}")
    if not isinstance(extracted, dict):
        return {}
    return {str(k): v for k, v in extracted.items() if v is not None}


def sidebar_chat_navigation():
    st.sidebar.header("Chats")
    if st.sidebar.button("New Chat"):
        add_new_chat()
    st.sidebar.divider()

    for chat in list(st.session_state.chats):
        is_active = chat["id"] == st.session_state.active_chat_id
        label = f"➡️ {chat['title']}" if is_active else chat["title"]
        cols = st.sidebar.columns([0.7, 0.2])
        if cols[0].button(label, key=f"select_{chat['id']}"):
            st.session_state.active_chat_id = chat["id"]
        cols[0].caption(chat["timestamp"])
        if cols[1].button("✕", key=f"delete_{chat['id']}"):
            delete_chat(chat["id"])


def render_memory_panel():
    with st.sidebar.expander("User Memory", expanded=True):
        memory = st.session_state.get("memory", {})
        if memory:
            for key, value in memory.items():
                st.write(f"- **{key}**: {value}")
        else:
            st.write("No memory stored yet.")
        if st.button("Clear memory", key="clear_memory"):
            reset_memory()


def main():
    st.set_page_config(page_title="My AI Chat", layout="wide")
    st.title("My AI Chat")

    hf_token = st.secrets.get("HF_TOKEN")
    if not hf_token:
        st.error(
            "Hugging Face token missing. Add `HF_TOKEN = \"<your-token>\"` to `.streamlit/secrets.toml` "
            "and restart the app to continue."
        )
        return

    if "memory" not in st.session_state:
        st.session_state.memory = load_memory()
    if "memory_error" not in st.session_state:
        st.session_state.memory_error = None
    if st.session_state.memory_error:
        st.warning(st.session_state.memory_error)
        st.session_state.memory_error = None

    ensure_chat_state()
    sidebar_chat_navigation()
    render_memory_panel()
    active_chat = get_active_chat()

    if not active_chat:
        st.info("Create a chat from the sidebar to begin.")
        return

    st.subheader(f"Active chat: {active_chat['title']}")
    render_history(active_chat["history"])

    user_input = st.chat_input("Type your message here...")
    if not user_input:
        return

    active_chat["history"].append({"role": "user", "content": user_input})
    active_chat["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persist_chat(active_chat)

    assistant_text = ""
    with st.spinner("Contacting the Hugging Face router..."):
        try:
            with st.chat_message("assistant"):
                assistant_placeholder = st.empty()
                for chunk in stream_hf_chat(
                    active_chat["history"], st.session_state.memory, hf_token
                ):
                    assistant_text += chunk
                    assistant_placeholder.markdown(assistant_text)
        except RuntimeError as exc:
            st.error(str(exc))
            return

    assistant_placeholder.empty()
    if assistant_text:
        active_chat["history"].append({"role": "assistant", "content": assistant_text})
        active_chat["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        persist_chat(active_chat)

    try:
        extracted_memory = extract_memory_from_message(user_input, hf_token)
    except RuntimeError as exc:
        st.session_state.memory_error = str(exc)
    else:
        update_memory_from_extraction(extracted_memory)



if __name__ == "__main__":
    main()
