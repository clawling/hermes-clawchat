"""Public package surface for the ClawChat Hermes gateway adapter.

Do not eagerly import :mod:`clawchat_gateway.adapter` here. The adapter
does ``from gateway.config import Platform`` at module level. Keeping the
import lazy avoids stale ``Platform`` references in legacy patched installs
and avoids importing Hermes gateway modules before modern
``ctx.register_platform`` registration has provided the runtime config.
Consumers should import the adapter directly:
``from clawchat_gateway.adapter import ClawChatAdapter``.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
