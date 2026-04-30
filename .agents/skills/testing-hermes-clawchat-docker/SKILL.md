---
name: testing-hermes-clawchat-docker
description: Use when testing hermes-clawchat against Dockerized Hermes agent images, real ClawChat activation codes, matrix runs, or optional Android adb chat verification.
---

# Testing Hermes ClawChat Docker

## Overview

Use this skill to run Hermes ClawChat E2E tests against Docker images. Core principle: one test run proves exactly one behavior. Do not bundle activation, profile, nickname, friends, media, or Android checks into one success signal.

## Quick Reference

| Item | Rule |
| --- | --- |
| Image list | Read `.e2e/images.tsv`, one Docker image per line. |
| Run home | Copy `.e2e/hermes-home-backup/` into `.e2e/runs/<tag>/<test-name>/home/`. |
| Logs | Write `.e2e/logs/<tag>-<test-name>.log`. |
| Image tag | Use the Docker tag as `<tag>`, e.g. `latest`, `v2026.4.23`. |
| Code source | Fetch `data.code` from `http://company.newbaselab.com:19001/v1/agents/connect-codes`. |
| adb | Ask the user once before any adb test. Do not probe `adb devices` first. |

## Required Flow

1. Identify the single behavior under test: activation, profile query, nickname update, friends list, media upload, or Android real-chat activation.
2. If Android adb might be involved, ask: `这次是否需要 Android adb 真实聊天测试？` Wait for the answer.
3. For each image in `.e2e/images.tsv`, create a fresh isolated home from `.e2e/hermes-home-backup/` under `.e2e/runs/<tag>/<test-name>/home/`.
4. Start the image with that home mounted as `HERMES_HOME=/opt/data` and the plugin repo mounted into the container.
5. Install the current repo plugin and run the ClawChat installer against the container Hermes directory.
6. Run only the selected behavior. Stop after its assertions pass or fail.
7. Save logs per image and report pass/fail per image.

## Activation Test

Docker-only activation uses `hermes chat` and the remote code endpoint.

Input exactly one natural-language activation message:

```text
clawchat 的激活码是 <code>
```

Success requires `config.yaml` in that image's run home to contain `platforms.clawchat.extra.token`, `user_id`, `base_url`, and `websocket_url`. Do not continue to profile queries, nickname updates, friends list, or uploads in the same test.

## Android adb Test

Run this only after the user says adb is needed. The user will connect a phone. Verify `adb devices` only after consent.

For Android real-chat activation, the single behavior is: get an activation code through the phone flow, send the activation message from the phone ClawChat app, and confirm the phone receives a normal Hermes reply. Success requires both Hermes config activation and a visible phone reply. Do not add profile, nickname, friends, or media checks to this same run.

## Example

For `nousresearch/hermes-agent:v2026.4.23` and test `activate`:

```text
home: .e2e/runs/v2026.4.23/activate/home/
log:  .e2e/logs/v2026.4.23-activate.log
assertion: home/config.yaml has clawchat token/user_id/base_url/websocket_url
```

## Common Rationalizations

| Excuse | Reality |
| --- | --- |
| `We are already activated, so query profile too.` | That creates a multi-feature test. Start a separate profile test. |
| `One smoke bundle is faster.` | Bundles hide root cause and violate one behavior per run. |
| `adb devices is harmless.` | The user required an adb decision first. Ask before probing. |
| `Share one run home unless it fails.` | Shared homes cause cross-image contamination. Always isolate first. |

## Red Flags

- A test name like `full`, `all-tools`, `smoke-bundle`, or `activate-and-profile`.
- More than one ClawChat tool or user-visible feature in a single run.
- Reusing `.e2e/run-home` or one run home across multiple image tags.
- Running `adb devices` before asking the user whether adb is needed.
- Marking Android success without checking the phone received a Hermes reply.

## Common Mistakes

- Treating `latest` and versioned images as one environment. Each tag gets its own home and log.
- Trusting model text alone. Prefer stable assertions such as `config.yaml` contents for activation.
- Reusing an activation code across images. Fetch a fresh code per image run.
- Turning an activation test into a general tool-call test. Keep tool-call tests separate.
