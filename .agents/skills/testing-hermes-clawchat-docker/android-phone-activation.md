# Android Phone Activation Reference

Use this reference only after the user explicitly agrees to Android adb testing. The single behavior is real-phone activation. The one visible phone reply is only the confirmation that activation produced a usable ClawChat connection.

## ADB Discovery

Do not run adb before consent. After consent, find it in this order:

```bash
command -v adb
printf '%s\n' "$ANDROID_HOME/platform-tools/adb" "$ANDROID_SDK_ROOT/platform-tools/adb" "$HOME/Library/Android/sdk/platform-tools/adb"
command -v flutter
```

Use the first executable adb path. On macOS with Android Studio/Flutter, `$HOME/Library/Android/sdk/platform-tools/adb` is common.

## Server First

Before phone UI actions, ensure Hermes is actually serving ClawChat:

```bash
docker ps --filter "name=<container>" --format "{{.Names}} {{.Status}}"
docker exec <container> sh -lc 'HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes gateway status'
docker exec <container> sh -lc 'tail -n 120 /opt/data/logs/agent.log'
```

Proceed only after logs show the ClawChat WebSocket reaches `ready` or equivalent connected state.

## Phone Flow

1. Launch ClawChat: `adb shell monkey -p com.newbaselab.clawchat -c android.intent.category.LAUNCHER 1`.
2. Open `联系人`.
3. Tap `创建 Agent`.
4. Choose `连接 Hermes Agent`.
5. Read the generated `connect <CODE>` instruction from the screen.
6. Activate the container with that phone-generated code.
7. Wait for the phone to show the new Agent chat as online.
8. Send one simple message, e.g. `ping`, only to confirm the activated connection works.
9. Activation success requires a visible phone reply, e.g. `pong`, and Hermes logs showing inbound + response ready.

## Activation Command

Use the mounted repo source in the container. Do not require `pip`; Hermes images may not include it in the venv.

```bash
docker exec <container> sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes PYTHONPATH=/work/plugin/src:/work/plugin /opt/hermes/.venv/bin/python -m clawchat_gateway.activate <CODE>'
```

Then verify config fields:

```bash
docker exec <container> sh -lc 'HERMES_HOME=/opt/data PYTHONPATH=/work/plugin/src:/work/plugin /opt/hermes/.venv/bin/python - <<"PY"
import os, yaml
from pathlib import Path
p = Path(os.environ["HERMES_HOME"]) / "config.yaml"
c = yaml.safe_load(p.read_text()) or {}
extra = c.get("platforms", {}).get("clawchat", {}).get("extra", {})
print({k: bool(extra.get(k)) for k in ["token", "user_id", "base_url", "websocket_url"]})
PY'
```

## Loading Or No Reply Recovery

If the phone shows online but no reply appears:

1. Check Hermes first: gateway status, `agent.log`, and `gateway.log`.
2. Confirm logs show ClawChat WebSocket `ready` and inbound message receipt.
3. Press Android Back to return to the chat list or previous page.
4. Re-enter the Agent chat.
5. Retry one simple message such as `ping`.
6. Do not mark activation success until the phone visibly receives a Hermes reply.

Do not treat this as a general chat feature test. Do not escalate to broad retries, profile checks, nickname changes, or media tests in this run. If installer compatibility fails, stop and fix that root cause with TDD before continuing.
