from __future__ import annotations


def santize_message(msg: str) -> str:
    # We really only need to escape < and >
    return msg.replace("<", "&lt;").replace(">", "&gt;")
