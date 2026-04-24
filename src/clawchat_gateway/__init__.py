"""Public package surface for the ClawChat Hermes gateway adapter.

Do not eagerly import :mod:`clawchat_gateway.adapter` here. The adapter
does ``from gateway.config import Platform`` at module level and our
anchor-patch adds ``Platform.CLAWCHAT`` to that enum; importing adapter
before the plugin's ``register()`` has applied the patch binds a stale
``Platform`` reference (without ``CLAWCHAT``) into the adapter module,
and later ``super().__init__(..., Platform.CLAWCHAT)`` raises
``AttributeError`` even after we reload ``gateway.config``. Consumers
should import the adapter directly: ``from clawchat_gateway.adapter
import ClawChatAdapter``.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
