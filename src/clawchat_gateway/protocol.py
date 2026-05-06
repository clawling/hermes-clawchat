from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def new_frame_id(prefix: str = "req") -> str:
    return f"{prefix}-{uuid.uuid4()}"


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
    payload = frame.get("payload")
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("nonce"), str):
        return payload["nonce"]
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("nonce"), str):
        return data["nonce"]
    return None


def is_hello_ok(frame: dict[str, Any], expected_request_id: str) -> bool:
    if frame.get("event") == "hello-ok":
        return True
    payload = frame.get("payload")
    if not isinstance(payload, dict):
        return False
    return (
        frame.get("type") == "res"
        and frame.get("requestId") == expected_request_id
        and payload.get("type") == "hello-ok"
    )


def build_connect_request(
    *,
    frame_id: str,
    token: str,
    client_id: str,
    client_version: str,
    sign: str,
    device_id: str | None = None,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token": token,
        "client_id": client_id,
        "client_version": client_version,
        "sign": sign,
    }
    if device_id is not None:
        payload["device_id"] = device_id
    if capabilities is not None:
        payload["capabilities"] = capabilities
    return {
        "version": "2",
        "event": "connect",
        "trace_id": frame_id,
        "payload": payload,
    }


def _message_envelope(
    event: str,
    *,
    chat_id: str,
    chat_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "2",
        "event": event,
        "trace_id": new_frame_id("trace"),
        "chat_id": chat_id,
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
        payload={"message_id": message_id},
    )


def build_message_add_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
    full_text: str,
    delta: str,
    sequence: int,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return _message_envelope(
        "message.add",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={
            "message_id": message_id,
            "sequence": sequence,
            "mutation": {"type": "append", "target_fragment_index": None},
            "fragments": [{"kind": "text", "text": full_text, "delta": delta}],
            "streaming": {
                "status": "streaming",
                "sequence": sequence,
                "mutation_policy": "append_text_only",
                "started_at": None,
                "completed_at": None,
            },
            "added_at": now_ms,
        },
    )


def build_message_done_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
    fragments: list[dict[str, Any]],
    sequence: int,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return _message_envelope(
        "message.done",
        chat_id=chat_id,
        chat_type=chat_type,
        payload={
            "message_id": message_id,
            "fragments": fragments,
            "streaming": {
                "status": "done",
                "sequence": sequence,
                "mutation_policy": "append_text_only",
                "started_at": None,
                "completed_at": now_ms,
            },
            "completed_at": now_ms,
        },
    )


def build_message_reply_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
    fragments: list[dict[str, Any]],
    reply_to_message_id: str | None = None,
    include_message_id: bool = False,
) -> dict[str, Any]:
    context: dict[str, Any] = {"mentions": [], "reply": None}
    if reply_to_message_id:
        context["reply"] = {
            "reply_to_msg_id": reply_to_message_id,
            "reply_preview": None,
        }
    payload: dict[str, Any] = {
        "message_mode": "normal",
        "message": {
            "body": {"fragments": fragments},
            "context": context,
        },
    }
    if include_message_id:
        payload["message_id"] = message_id
    return _message_envelope(
        "message.reply",
        chat_id=chat_id,
        chat_type=chat_type,
        payload=payload,
    )


def build_message_failed_event(
    *,
    chat_id: str,
    chat_type: str,
    message_id: str,
    sequence: int,
    reason: str | None = None,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    reason_text = reason or "unknown"
    payload: dict[str, Any] = {
        "message_id": message_id,
        "sequence": sequence,
        "reason": reason_text,
        "streaming": {
            "status": "failed",
            "sequence": sequence,
            "mutation_policy": "append_text_only",
            "started_at": None,
            "completed_at": now_ms,
        },
        "completed_at": now_ms,
    }
    if reason and reason.strip():
        payload["fragments"] = [{"kind": "text", "text": reason.strip()}]
    return _message_envelope(
        "message.failed",
        chat_id=chat_id,
        chat_type=chat_type,
        payload=payload,
    )


def build_typing_update_event(
    *,
    chat_id: str,
    chat_type: str,
    active: bool,
) -> dict[str, Any]:
    return {
        "version": "2",
        "event": "typing.update",
        "trace_id": new_frame_id("trace"),
        "chat_id": chat_id,
        "payload": {"is_typing": active},
    }
