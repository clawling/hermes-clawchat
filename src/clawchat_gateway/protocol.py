from __future__ import annotations

import hashlib
import hmac
import itertools
import json
from typing import Any

_counter = itertools.count(1)


def new_frame_id(prefix: str = "req") -> str:
    return f"{prefix}-{next(_counter)}"


def encode_frame(frame: dict[str, Any]) -> str:
    return json.dumps(frame, separators=(",", ":"), ensure_ascii=False)


def decode_frame(text: str) -> dict[str, Any]:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("frame must be object")
    return obj


def compute_client_sign(client_id: str, nonce: str, token: str) -> str:
    return hmac.new(
        token.encode("utf-8"),
        f"{client_id}|{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def extract_nonce(frame: dict[str, Any]) -> str | None:
    payload = frame.get("payload") or {}
    if isinstance(payload.get("nonce"), str):
        return payload["nonce"]
    data = payload.get("data") or {}
    if isinstance(data.get("nonce"), str):
        return data["nonce"]
    return None


def is_hello_ok(frame: dict[str, Any], expected_request_id: str) -> bool:
    return (
        frame.get("type") == "res"
        and frame.get("requestId") == expected_request_id
        and (frame.get("payload") or {}).get("type") == "hello-ok"
    )


def build_connect_request(
    *,
    frame_id: str,
    token: str,
    client_id: str,
    client_version: str,
    sign: str,
) -> dict[str, Any]:
    return {
        "type": "req",
        "id": frame_id,
        "method": "connect",
        "params": {
            "auth": {"token": token},
            "client": {
                "id": client_id,
                "version": client_version,
                "sign": sign,
            },
        },
    }


def _message_envelope(
    event: str,
    *,
    chat_id: str,
    chat_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "event",
        "id": new_frame_id("evt"),
        "event": event,
        "chat_id": chat_id,
        "chat_type": chat_type,
        "payload": payload,
    }


def build_message_created_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
) -> dict[str, Any]:
    return _message_envelope(
        "message.created",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={"message": {"id": message_id}},
    )


def build_message_add_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
    full_text: str,
    delta: str,
) -> dict[str, Any]:
    return _message_envelope(
        "message.add",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={
            "message": {
                "id": message_id,
                "fragments": [{"kind": "text", "text": full_text, "delta": delta}],
            }
        },
    )


def build_message_done_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
) -> dict[str, Any]:
    return _message_envelope(
        "message.done",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={"message": {"id": message_id}},
    )


def build_message_reply_event(
    *,
    chat_id: str,
    chat_type: str,
    fragments: list[dict[str, Any]],
    reply_to_message_id: str | None = None,
) -> dict[str, Any]:
    context = {}
    if reply_to_message_id:
        context["reply_to_message_id"] = reply_to_message_id
    return _message_envelope(
        "message.reply",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={"message": {"fragments": fragments, "context": context}},
    )
