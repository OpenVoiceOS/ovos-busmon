"""Message type glob filtering."""
from __future__ import annotations

import fnmatch
from typing import List


def matches_glob(msg_type: str, pattern: str) -> bool:
    """Return True if *msg_type* matches *pattern* (glob, case-insensitive).

    An empty or wildcard-only pattern always matches.
    """
    if not pattern or pattern == "*":
        return True
    return fnmatch.fnmatch(msg_type.lower(), pattern.lower())


def filter_by_type(messages: list, pattern: str) -> list:
    """Return only messages whose msg_type matches the glob *pattern*."""
    if not pattern or pattern == "*":
        return messages
    return [m for m in messages if matches_glob(m.msg_type, pattern)]
