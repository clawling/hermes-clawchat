# ClawChat Activation Env Secret Design

## Goal

Move ClawChat activation secrets out of `~/.hermes/config.yaml` and into `~/.hermes/.env`, while keeping the existing `/ws` WebSocket endpoint behavior.

## Scope

This change updates activation persistence only. It does not change the ClawChat WebSocket path, connection protocol, adapter streaming behavior, or remote service API shape.

## Current Behavior

`clawchat_gateway.activate.persist_activation()` writes activation data into `~/.hermes/config.yaml` under `platforms.clawchat.extra`. That includes non-secret values such as `base_url`, `websocket_url`, and `user_id`, but also secret values such as `token` and `refresh_token`.

The default ClawChat WebSocket URL is currently `ws://company.newbaselab.com:10086/ws`. This path must remain unchanged.

## Proposed Behavior

Activation writes credentials to `~/.hermes/.env`:

- `CLAWCHAT_TOKEN=<access token>`
- `CLAWCHAT_REFRESH_TOKEN=<refresh token>` when a refresh token is returned

Activation keeps non-secret runtime configuration in `~/.hermes/config.yaml`:

- `platforms.clawchat.enabled: true`
- `platforms.clawchat.extra.base_url`
- `platforms.clawchat.extra.websocket_url`
- `platforms.clawchat.extra.user_id`
- `platforms.clawchat.extra.reply_mode: stream`
- `platforms.clawchat.extra.show_tools_output: false`
- `platforms.clawchat.extra.show_think_output: false`
- existing streaming and display defaults

If `config.yaml` already contains `platforms.clawchat.extra.token` or `platforms.clawchat.extra.refresh_token`, activation removes those keys after writing the new `.env` values.

## WebSocket URL

The WebSocket URL remains `/ws`.

For the default NewBase base URL, activation continues to derive `ws://company.newbaselab.com:10086/ws`. Custom base URLs should also derive a WebSocket URL with the `/ws` path, using `wss` for HTTPS base URLs and `ws` otherwise.

## Components

`activate.py` owns persistence. It should gain a small helper for writing ClawChat env values, preferably using Hermes' own `hermes_cli.config.save_env_value()` when available and falling back to safe local `.env` update logic if activation is running outside a Hermes checkout.

`install.py` already injects `CLAWCHAT_TOKEN` support into hermes-agent config loading. It should also support `CLAWCHAT_REFRESH_TOKEN` so the refresh token remains available in `platform_config.extra` for future use without storing it in YAML.

`api_client.py` and connection code do not need protocol changes.

## Data Flow

1. User runs activation with an activation code.
2. Activation calls `/v1/agents/connect` and receives an access token, optional refresh token, and agent user id.
3. Activation writes token secrets to `~/.hermes/.env`.
4. Activation writes non-secret ClawChat settings to `~/.hermes/config.yaml`.
5. Activation schedules or instructs a Hermes gateway restart so the installed env override code reloads `CLAWCHAT_TOKEN`.

## Error Handling

If writing `.env` fails, activation should fail rather than silently saving only partial credentials. This prevents a misleading successful activation where the gateway cannot reconnect.

If `refresh_token` is absent, activation should remove any existing `CLAWCHAT_REFRESH_TOKEN` value instead of preserving a stale refresh token. Access token writing remains required.

## Testing

Tests should cover:

- activation writes `CLAWCHAT_TOKEN` and `CLAWCHAT_REFRESH_TOKEN` to `.env`
- activation removes `token` and `refresh_token` from `config.yaml`
- activation preserves `websocket_url` as `ws://company.newbaselab.com:10086/ws`
- activation derives custom base URL WebSocket values with `/ws`, not `/v1/ws`
- installer env override payload includes `CLAWCHAT_REFRESH_TOKEN`

## Non-Goals

- No migration command for existing installs beyond the next activation run.
- No WebSocket path change to `/v1/ws`.
- No token refresh implementation.
- No changes to ClawChat message send/receive behavior.
