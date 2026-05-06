# Android Phone Activation Reference

Use this reference only after the user explicitly agrees to Android adb testing. The single behavior is real-phone activation on Hermes v0.12.0+ using pluggable gateway platforms. The one visible phone reply is only the confirmation that activation produced a usable ClawChat connection.

Core rule: do not patch Hermes source for this flow. The ClawChat repo is mounted as a Hermes plugin, enabled with `hermes plugins enable clawchat`, and loaded through `ctx.register_platform(...)`. `python -m clawchat_gateway.install --hermes-dir ...` is a legacy fallback only for older Hermes builds without pluggable gateway platforms.

## ADB Discovery

Do not run adb before consent. After consent, find it in this order:

```bash
command -v adb
printf '%s\n' "$ANDROID_HOME/platform-tools/adb" "$ANDROID_SDK_ROOT/platform-tools/adb" "$HOME/Library/Android/sdk/platform-tools/adb"
command -v flutter
```

Use the first executable adb path. On macOS with Android Studio/Flutter, `$HOME/Library/Android/sdk/platform-tools/adb` is common.

## Container First

Before phone UI actions, verify the test container, model provider config, and v0.12 plugin setup. At this point ClawChat WebSocket may not be connected yet because the phone-generated activation code has not been exchanged for credentials.

```bash
docker ps --filter "name=<container>" --format "{{.Names}} {{.Status}}"
docker exec <container> sh -lc 'sed -n "1,8p" /opt/data/config.yaml'
docker exec <container> sh -lc 'grep -Ei "^(MINIMAX|OPENROUTER|OPENAI|ANTHROPIC|GOOGLE|GEMINI|DEEPSEEK|DASHSCOPE|MOONSHOT|ZHIPU|HERMES_INFERENCE_PROVIDER)" /opt/data/.env | sed -E "s/=.*/=***REDACTED***/"'
docker exec <container> sh -lc 'mkdir -p /opt/data/plugins && ln -sfn /work/plugin /opt/data/plugins/clawchat'
docker exec <container> sh -lc 'HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes plugins enable clawchat'
docker exec <container> sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes /opt/hermes/.venv/bin/hermes plugins list | grep clawchat'
```

Proceed only after the model provider is configured and the `clawchat` plugin is enabled. If model provider credentials are missing, stop and fix the run home; otherwise Hermes may activate the code via direct CLI but phone chat replies will fail with provider authentication errors.

## Phone Flow

1. Launch ClawChat: `adb shell monkey -p com.newbaselab.clawchat -c android.intent.category.LAUNCHER 1`.
2. Open `联系人`.
3. Tap `创建 Agent`.
4. Choose `连接 Hermes Agent`.
5. Copy or read the full generated Hermes prompt from the screen. It usually contains a one-time `connect <CODE>` activation code and install instructions.
6. Send the copied prompt to Hermes in the container. This is the primary Android test path because it verifies model/provider config, tool selection, activation, plugin registration, and gateway restart together.
7. Wait for the phone to show the new Agent chat as online.
8. Send one simple message, e.g. `ping`, only to confirm the activated connection works.
9. Activation success requires a visible phone reply, e.g. `pong`, and Hermes logs showing inbound + response ready.

## Prompt-Mediated Activation

Use the mounted repo source in the container and send the exact phone prompt to `hermes chat`. Do not require `pip`; Hermes images may not include it in the venv. Do not run the legacy patch installer.

```bash
docker exec -i <container> sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes PYTHONPATH=/work/plugin/src:/work/plugin /opt/hermes/.venv/bin/hermes chat -q "$(cat)"' <<'EOF'
<PASTE_THE_FULL_PHONE_PROMPT_HERE>
EOF
```

If the prompt-mediated path fails before tool execution because the model/provider is not configured, stop and fix the run home. Do not silently switch to direct CLI activation and mark Android success; that would skip the behavior under test.

## Direct CLI Fallback

Use direct CLI activation only when explicitly isolating gateway/adapter behavior after model-provider failure has already been diagnosed. It does not prove Hermes can follow the phone prompt.

```bash
docker exec <container> sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes PYTHONPATH=/work/plugin/src:/work/plugin /opt/hermes/.venv/bin/python -m clawchat_gateway.activate <CODE>'
```

Activation writes secrets to `.env` and non-secret platform settings to `config.yaml`:

```bash
docker exec <container> sh -lc 'HERMES_HOME=/opt/data PYTHONPATH=/work/plugin/src:/work/plugin /opt/hermes/.venv/bin/python - <<"PY"
import os, yaml
from pathlib import Path
home = Path(os.environ["HERMES_HOME"])
c = yaml.safe_load((home / "config.yaml").read_text()) or {}
extra = c.get("platforms", {}).get("clawchat", {}).get("extra", {})
env = {}
for line in (home / ".env").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
print({
    "enabled": c.get("platforms", {}).get("clawchat", {}).get("enabled") is True,
    "config": {k: bool(extra.get(k)) for k in ["user_id", "base_url", "websocket_url"]},
    "env": {k: bool(env.get(k)) for k in ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]},
    "secrets_not_in_config": "token" not in extra and "refresh_token" not in extra,
})
PY'
```

After activation, the CLI schedules a detached `hermes gateway restart`. Verify readiness from logs:

```bash
docker exec <container> sh -lc 'sleep 5; tail -n 160 /opt/data/logs/agent.log | grep -Ei "registered Hermes platform|Connecting to clawchat|clawchat connected|handshake complete|state -> ready|Provider authentication failed|config validation failed"'
```

Proceed to the phone confirmation only after logs show:

- `ClawChat registered Hermes platform via plugin registry`
- `Connecting to clawchat`
- `✓ clawchat connected`
- `clawchat ws handshake complete`
- `clawchat state -> ready`

## Loading Or No Reply Recovery

If the phone shows online but no reply appears:

1. Check Hermes first: gateway status, `agent.log`, and `gateway.log`.
2. Confirm logs show ClawChat WebSocket `ready` and inbound message receipt.
3. Press Android Back to return to the chat list or previous page.
4. Re-enter the Agent chat.
5. Retry one simple message such as `ping`.
6. Do not mark activation success until the phone visibly receives a Hermes reply.

If logs show `Provider authentication failed` or `No inference provider configured`, the Android activation path is blocked by the Hermes run home's model provider config, not by ClawChat activation. Fix the run home and restart the run.

If logs show `config validation failed` with ClawChat after activation, inspect whether `.env` contains both `CLAWCHAT_TOKEN` and `CLAWCHAT_REFRESH_TOKEN`, and whether `config.yaml` contains `platforms.clawchat.extra.websocket_url`. On Hermes v0.12.0+, this should work through plugin platform registration; do not fall back to source patching unless explicitly testing legacy Hermes.

Do not treat this as a general chat feature test. Do not escalate to broad retries, profile checks, nickname changes, or media tests in this run. If v0.12 plugin registration fails, stop and fix that root cause with TDD before continuing.
