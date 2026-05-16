# AGENTS.md

Guidance for coding agents working in this repository.

## Project overview

This repository is a Hermes Agent plugin that integrates the ClawChat messaging platform.

- The plugin targets the Hermes v0.12.0+ plugin/platform API.
- The plugin entrypoint is `__init__.py` at the repository root.
- The plugin manifest is `plugin.yaml`.
- The gateway adapter package is `clawchat_gateway/`.
- The local Hermes Agent source checkout under `tmp/hermes-agent/` is the reference for host APIs, platform contracts, and Hermes release behavior.

## Documentation index

Use `docs/` as the source of truth for implementation details.

- `docs/README.md` — documentation index and per-module catalogue.
- `docs/architecture.md` — boot sequence, runtime data flow, design choices, and environment-variable overview.
- `docs/plugin-entrypoint.md` — plugin entrypoint, registration behavior, and manifest relationship.
- `docs/config.md` — configuration fields and environment-variable resolution.
- `docs/adapter.md`, `docs/connection.md`, `docs/inbound.md`, `docs/protocol.md` — gateway runtime and protocol-builder behavior.
- `docs/clawchat-protocol-reference.md` — ClawChat wire-protocol reference.
- `docs/plugin-tools.md`, `docs/tools.md` — Hermes tool schemas, registration, and handlers.
- `docs/activate.md`, `docs/cli.md`, `docs/commands.md`, `docs/setup.md` — activation, native CLI, slash command, and gateway setup flows.
- `docs/media-runtime.md`, `docs/profile.md`, `docs/runtime-defaults.md` — media handling, profile CLI, and startup defaults.
- `docs/tests.md` — unit-test harness, fake Hermes runtime, and test coverage map.
- `.e2e/docs/testing.md` — E2E test documentation for the real Hermes/ClawChat environment harness.

## Project constraints

- Keep `AGENTS.md` limited to project orientation, documentation navigation, top-level collaboration rules, and test entry points. Do not put implementation details here.
- Keep code behavior, fields, protocols, lifecycle details, error handling, configuration resolution, compatibility notes, and API-contract details in the matching `docs/` files.
- Before changing a feature, read the relevant `docs/` page. After changing behavior, update the matching `docs/` page in the same change set.
- If Hermes Agent APIs or platform contracts change, consult `tmp/hermes-agent/` source and changelogs first, then update the relevant code and `docs/` files.
- Treat `tmp/hermes-agent/` as a host API reference. Do not solve plugin requirements by patching that checkout.
- Do not write, fabricate, or guess secrets.

## Test cases

- Default unit-test command: `pytest`.
- Single-test command: `pytest tests/test_x.py::test_name`.
- Unit-test selection guide: `docs/tests.md`.
- Real-environment E2E test documentation: `.e2e/docs/testing.md`.
