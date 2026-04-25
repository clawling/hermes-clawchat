# hermes-clawchat Conformance Report

> Original evaluation against [`custom-gateway-guide.md`](./custom-gateway-guide.md) on 2026-04-24.
> Re-evaluated on 2026-04-25 against `/Users/joe/dev/nb/code/dependence-library/hermes-agent` (reference checkout).
> Target: package `clawchat-gateway` v0.1.0, distributed **out-of-tree as a hermes-agent plugin**.

## Scope clarification (2026-04-25)

`hermes-clawchat` is shipped **only** as an installable plugin. It will **not** be merged into hermes-agent's tree. This reframes which items in the original 16-point checklist are in-scope:

- **In-scope for the plugin:** anchor patches that affect *runtime message flow* — adapter wiring, env-var ingestion, allowlists used at message-handling time, and routing maps used by tools/cron/webhook delivery.
- **Out-of-scope for the plugin (upstream concern):** hermes-agent's CLI surfaces (`status.py`, `dump.py`, `tools_config.py`, gateway setup wizard), upstream website docs, and generic redaction patterns. Patching these from a plugin would be overreach into hermes-agent's UX surface.

Items in the original checklist that map to upstream-only surfaces are now marked **N/A (upstream)**.

## TL;DR

`hermes-clawchat` is a **well-engineered Level 1 platform adapter** distributed **out-of-tree**. It correctly subclasses `BasePlatformAdapter` and implements all four required methods plus a rich set of optional ones. Because hermes-agent has no platform-plugin API, integration is via **anchor-patching hermes-agent's core files at install time**.

Since the original report:

- ✅ **Cron `platform_map` bug fixed** (commit `60b3850`) — `cron_platform_map` patch added.
- ✅ **Cron known-delivery-platforms list fixed** (same commit) — `cron_known_delivery_platforms` patch added.
- ✅ **Startup auth-map allowlists patched** — `startup_any_allowlist` and `startup_allow_all` cover the 3003/3025 maps.
- ✅ **`update_allowed_platforms` patched** — `Platform.CLAWCHAT` added to the broadcast allowlist.

**Two real runtime gaps remain** after the scope re-cut:

1. **Webhook cross-platform delivery** silently rejects `deliver="clawchat"` (structurally identical to the cron bug just fixed).
2. **Unauthorized-DM behavior map** (`gateway/run.py:3156`) does not see `CLAWCHAT_ALLOWED_USERS`, so unauthorized DMs fall through to `"pair"` instead of `"ignore"`. Blocked by `apply_patch`'s first-match limitation — the QQBOT anchor matches twice.

**Overall verdict: substantially conformant for runtime message flow; two runtime patches still owed.**

---

## 1. Integration Mechanism

### 1.1 hermes-agent's plugin system — what it covers

`hermes-agent/hermes_cli/plugins.py` defines a plugin loader that discovers plugins from `plugins/`, `~/.hermes/plugins/`, `./.hermes/plugins/`, and pip entry-points (group `hermes_agent.plugins`). The plugin API supports tools, hooks, skills, CLI commands, and backend providers.

### 1.2 What the plugin system does NOT cover

**Platforms are not pluggable.** Platform registration is hardcoded in:

- `gateway/config.py` — `Platform` enum.
- `gateway/run.py` — `_create_adapter()` if/elif chain; `_is_user_authorized()` and `_get_unauthorized_dm_behavior()` env maps.
- `cron/scheduler.py` — cron delivery routing maps.
- `tools/send_message_tool.py` — agent-tool routing map.
- `gateway/platforms/webhook.py` — webhook cross-delivery allowlist.

There is no hook, no entry-point group, and no registry to add new platforms dynamically.

### 1.3 clawchat's workaround: anchor-patching

`src/clawchat_gateway/install.py::build_patches()` defines **16 named patches** (post-fix). Each:

- Targets a file under a hermes-agent installation directory.
- Finds an **anchor string** (e.g., `'"qqbot": Platform.QQBOT,'`).
- Inserts a clawchat-specific payload before or after the anchor.
- Wraps the inserted code in `# clawchat-gateway:<patch_id>:start` / `:end` markers for idempotent re-apply and clean removal.

Patches are applied at plugin registration time via `__init__.py::_install_gateway()`, then `_refresh_gateway_module_cache()` reloads `gateway.config`, `gateway.run`, and `clawchat_gateway.adapter` so the new `Platform.CLAWCHAT` enum value is visible in the running process.

**Anchor-patching is a legitimate pragmatic workaround** for out-of-tree distribution, but it is fragile — any upstream rename of an anchor string silently breaks the integration.

---

## 2. Level 1 Conformance — `BasePlatformAdapter` Contract

| Contract element | Status | Evidence |
|---|---|---|
| Subclass `BasePlatformAdapter` | ✓ | `adapter.py:104` `class ClawChatAdapter(BasePlatformAdapter):` |
| `__init__` passes `Platform.CLAWCHAT` to base | ✓ | `adapter.py:108-110` |
| `async def connect() -> bool` | ✓ | `adapter.py:121` |
| `async def disconnect() -> None` | ✓ | `adapter.py:125` |
| `async def send(...) -> SendResult` | ✓ | `adapter.py:266` |
| `async def get_chat_info(chat_id)` | ✓ | `adapter.py:128` |
| `send_typing` / `stop_typing` | ✓ | `adapter.py:131`, `adapter.py:145` |
| `send_image` / `send_image_file` | ✓ | `adapter.py:455`, `adapter.py:472` |
| `edit_message` (streaming, finalize kwarg) | ✓ | `adapter.py:347` (commit `4bb1bad` accepts `finalize=`) |
| `on_run_complete` (custom hook) | ✓ | `adapter.py:393` |
| Uses `self.build_source(...)` | ✓ | `adapter.py:197-202` |
| Constructs `MessageEvent` correctly | ✓ | `adapter.py:206-219` |
| Calls `self.handle_message(event)` | ✓ | `adapter.py:232` |
| Inbound media caching | ✓ | `adapter.py:247-264` |
| Outbound media upload | ✓ | `adapter.py:595-611` |
| Returns `SendResult` on all paths | ✓ | success / error / edit |

**Contract conformance: full.**

---

## 3. Registration Checklist — Re-scoped for Plugin Distribution

| # | Original guide item | Patch id / location | Status | Notes |
|---|---|---|---|---|
| 1 | Add `Platform` enum entry | `platform_enum` → `gateway/config.py` | ✓ | Anchored on `QQBOT = "qqbot"`. |
| 2 | Adapter class + `check_*_requirements()` | `clawchat_gateway/adapter.py` | ✓ (out-of-tree) | Lives in plugin package. |
| 3 | `_create_adapter` factory branch | `adapter_factory` → `gateway/run.py` | ✓ | |
| 4 | `_apply_env_overrides` (env vars) | `env_overrides` → `gateway/config.py` | ✓ | Reads `CLAWCHAT_TOKEN`, `CLAWCHAT_WEBSOCKET_URL`, etc. |
| 5 | Auth allowlist maps (startup) | `auth_maps_allowed`, `auth_maps_allow_all`, `startup_any_allowlist`, `startup_allow_all` → `gateway/run.py` | ✓ | Covers 3003 / 3025 maps and the runtime startup pair at 1985 / 2000. |
| 5b | **Unauthorized-DM behavior map** (`gateway/run.py:3156`) | — | **✗ runtime gap** | Third allowlist map inside `_get_unauthorized_dm_behavior`. Blocked by anchor ambiguity (see §4.2). |
| 6 | `PLATFORM_HINTS` in prompt builder | `prompt_hints` → `agent/prompt_builder.py` | ✓ | |
| 7 | `toolsets.py` entry | — | N/A (plugin) | Tools registered via `register(ctx)`. |
| 8 | Cron scheduler `platform_map` | `cron_platform_map` → `cron/scheduler.py` | ✓ | Fixed in commit `60b3850`. |
| 8b | Cron `_KNOWN_DELIVERY_PLATFORMS` set | `cron_known_delivery_platforms` → `cron/scheduler.py` | ✓ | Fixed in commit `60b3850`. |
| 9 | `send_message_tool.py` routing map | `send_message_tool` → `tools/send_message_tool.py` | ✓ | |
| 9b | **Webhook cross-platform delivery list** (`gateway/platforms/webhook.py`) | — | **✗ runtime gap** | Unpatched. `webhook → deliver="clawchat"` silently fails. See §4.1. |
| 10 | `cronjob_tools.py` parameter description | — | N/A (upstream) | Description is generic/illustrative; not a routing map. |
| 11 | `channel_directory.py` session-fallback list | — | ✓ (auto-handled) | `for plat in Platform:` loop covers any new enum value via `_build_from_sessions()`. No patch required. |
| 12 | `hermes_cli/status.py` row | — | N/A (upstream) | CLI UX surface owned by hermes-agent. |
| 13 | CLI setup wizard entry | `cli_platform_registry` → `hermes_cli/platforms.py` | ✓ | |
| 14 | `agent/redact.py` PII patterns | — | N/A (upstream) | No platform-specific patterns exist for any platform; redaction is generic. |
| 15 | Integration test against patched hermes-agent | — | ✗ | Still missing. See §4.3. |
| 16 | User-facing docs in `website/docs/` | — | N/A (upstream) | Plugin owns its own `docs/`. |
| 17 | Streaming/connected-platforms gating | `connected_platforms`, `update_allowed_platforms` → `gateway/config.py`, `gateway/run.py` | ✓ | Added since original report. |
| 18 | `on_run_complete` hooks | `post_stream_hook`, `normal_stream_done_hook` → `gateway/run.py` | ⚠ verify | `post_stream_hook` anchor matches 3 sites; only the first is patched. See §4.4. |

**Plugin-scoped registration score: 14 ✓ / 5 N/A / 2 runtime gaps / 1 verify / 1 missing test.**

---

## 4. Outstanding Gaps & Risks

### 4.1 Webhook cross-platform delivery — runtime silent failure

**File:** `gateway/platforms/webhook.py:213-224`. Hardcoded allowed-`deliver_type` tuple does not include `"clawchat"`. A webhook configured with `deliver="clawchat"` falls through to `logger.warning("[webhook] Unknown deliver type: %s", ...)` and returns `success=False`.

This is structurally identical to the just-fixed cron `_KNOWN_DELIVERY_PLATFORMS` bug.

**Fix:** add a patch anchored on `'"qqbot",'` in `gateway/platforms/webhook.py` (the anchor is unique within that file at line 223), payload `'"clawchat",\n'`, `insert_after=True`, `indent_to_anchor=True`.

### 4.2 Unauthorized-DM behavior map — runtime auth gap

**File:** `gateway/run.py:3156`, inside `_get_unauthorized_dm_behavior`. There are **three** `platform_env_map`-shaped dicts in `run.py`:

| Line | Function | Status |
|---|---|---|
| 3003 | `_is_user_authorized` allowlist map | ✓ patched |
| 3025 | `_is_user_authorized` allow-all map | ✓ patched |
| 3156 | `_get_unauthorized_dm_behavior` allowlist map | ✗ unpatched |

Effect: with `CLAWCHAT_ALLOWED_USERS` set, the gateway's `_get_unauthorized_dm_behavior(Platform.CLAWCHAT)` does not see the env var, so unauthorized DMs land in the default `"pair"` branch instead of `"ignore"`. Inconsistent with how every other platform's allowlist behaves.

**Blocker:** the existing `auth_maps_allowed` patch's anchor `'Platform.QQBOT: "QQ_ALLOWED_USERS",'` matches **both** maps (3003 and 3156), and `apply_patch` returns on the first hit. Two ways forward:

- **(a) More specific anchor** — the 3156 entry uses 4-space alignment: `Platform.QQBOT:    "QQ_ALLOWED_USERS",` (note the multiple spaces). Adding a second `Patch` keyed on that exact whitespace pattern lands in the 3156 map only.
- **(b) Extend `apply_patch`** with `apply_all=True` or `occurrence=N`. More general, but needs additional test coverage and idempotency reasoning per occurrence.

Recommendation: (a) is the lower-risk fix.

### 4.3 No end-to-end integration test against a patched hermes-agent

The installer is unit-tested in isolation (`test_install.py` checks patch strings land), and the adapter is unit-tested with `fake_hermes.py` stubs. Neither verifies the two halves work together.

The reference checkout at `/Users/joe/dev/nb/code/dependence-library/hermes-agent` makes this cheap. A smoke test should:

1. Copy the reference tree to a tmpdir.
2. Run `install.main(["--hermes-dir", tmp])`.
3. Import `gateway.config` and assert `Platform.CLAWCHAT` exists.
4. Call `_create_adapter(Platform.CLAWCHAT, cfg)` and assert an instance is returned.
5. Assert cron `platform_map["clawchat"] is Platform.CLAWCHAT`.
6. Assert webhook `_deliver_cross_platform` accepts `"clawchat"` (post §4.1 fix).
7. Assert `_get_unauthorized_dm_behavior(Platform.CLAWCHAT)` returns `"ignore"` when `CLAWCHAT_ALLOWED_USERS` is set (post §4.2 fix).

This single test would have caught the original cron bug, will catch §4.1 and §4.2 once fixed, and is the only durable defense against future anchor drift.

### 4.4 `post_stream_hook` anchor ambiguity

The anchor `await asyncio.wait_for(stream_task, timeout=5.0)` matches **3 sites** in `gateway/run.py` (lines 9264, 10716, 10826). `apply_patch` only inserts at the first (9264 — a finally block in a streaming-proxy result path). The actual end-of-stream cleanup is at line 10826 — but that path is already covered by the separate `normal_stream_done_hook` (anchor `# Clean up tracking`, uniquely located at 10834).

**Action:** verify whether `on_run_complete` is supposed to fire at line 9264. If not relevant to clawchat's flow, drop the patch. If relevant, narrow the anchor (e.g., include the surrounding `_stream_consumer.finish()` line for uniqueness).

### 4.5 Anchor-patching is fragile (architectural)

Every patch depends on an exact upstream string staying stable. The patch system has safety features (idempotency markers, `--check`, `--dry-run`, atomic rollback on failure since commit `8d1a9fa`), but no semantic test proves the patched gateway still functions. §4.3 closes this.

### 4.6 `apply_patch` first-match limitation

Surfaces in §4.2 (3-way auth map) and §4.4 (3-way stream wait). Worth either documenting the requirement that anchors be unique, or extending `apply_patch` with explicit occurrence-targeting. Documentation is the cheaper option for now.

### 4.7 Module-reload side effects

`__init__.py` reloads `gateway.config`, `gateway.run`, and `clawchat_gateway.adapter`. Code that previously imported `Platform` retains the stale enum class. Mitigated by registration running early in startup. Worth a note in the install README; not a known failure path.

---

## 5. Test Coverage Notes

`tests/` has thorough coverage of:

- Adapter protocol handling (`test_adapter.py`, `test_inbound.py`, `test_protocol.py`)
- Connection lifecycle with `fake_ws.py` (`test_connection.py`)
- Installer patch application (`test_install.py`)
- Activation, profile, device ID, config, API client, media runtime

**Gap:** no integration test exercises the patched hermes-agent. See §4.3.

---

## 6. Recommendations

Priority-ordered.

### Must-fix

1. **Webhook cross-platform delivery patch** (§4.1) — runtime silent failure. Direct twin of the cron `_KNOWN_DELIVERY_PLATFORMS` patch, trivial to add.

2. **Unauthorized-DM behavior map patch** (§4.2) — runtime auth inconsistency. Use the whitespace-disambiguated anchor `Platform.QQBOT:    "QQ_ALLOWED_USERS",` to land in `gateway/run.py:3156` only.

3. **End-to-end integration test** (§4.3) against `dependence-library/hermes-agent`. Single durable defense against anchor drift.

### Should-fix

4. **Verify or drop `post_stream_hook`** (§4.4). Anchor matches 3 sites; the first may not be the intended target.

5. **Document `apply_patch` first-match contract** (§4.6) in `install.py` so future patches with non-unique anchors are explicit about which occurrence they expect.

### Nice-to-have

6. **Upstream proposal:** advocate for a `provides_platforms` extension point in the plugin manifest. Would obsolete the entire patch set. Track as an upstream issue; not blocking for this plugin.

7. **Update `docs/custom-gateway-guide.md`** to document the anchor-patch pattern as the canonical out-of-tree distribution approach, with this plugin as the reference implementation.

### Explicitly out of scope (upstream concern)

- `hermes_cli/status.py`, `hermes_cli/dump.py`, `hermes_cli/tools_config.py`, gateway setup wizard rows — UX surfaces owned by hermes-agent.
- `agent/redact.py` — generic patterns only; no platform overrides exist.
- `cronjob_tools.py` parameter description — illustrative free text, not a routing surface.
- Upstream website docs.

---

## 7. Final Score Card

| Dimension | Score | Rationale |
|---|---|---|
| `BasePlatformAdapter` contract | 10 / 10 | All required + optional methods correctly implemented. |
| `MessageEvent` / `SendResult` construction | 10 / 10 | Full schema, correct use of `build_source` and media caching. |
| Plugin-scoped registration | 14 / 16 | Two runtime patches still owed (§4.1 webhook, §4.2 unauthorized-DM). |
| Plugin-system integration | 7 / 10 | `register(ctx)` for tools; anchor-patch for platform bits because no platform API exists. |
| Test coverage | 7 / 10 | Strong unit tests; no end-to-end integration test against a patched hermes-agent. |
| Documentation | 9 / 10 | Excellent internal docs; per-module reference now in sync (commit `cf5238d`). |
| **Overall** | **~8.5 / 10** | Meets Level 1 intent; two runtime gaps and an integration test to close. |

hermes-clawchat meets the spirit of the guide's Level 1 criteria and is a strong reference for out-of-tree platform plugins. After §4.1 and §4.2 land, runtime parity with in-tree platforms is essentially complete.
