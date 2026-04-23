"""Public package surface for the ClawChat Hermes gateway adapter."""

from clawchat_gateway.adapter import ClawChatAdapter, check_clawchat_requirements

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ClawChatAdapter",
    "check_clawchat_requirements",
]
