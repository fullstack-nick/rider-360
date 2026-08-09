from __future__ import annotations

import hashlib


def stable_hex(namespace: str, *parts: object, length: int = 24) -> str:
    payload = "|".join([namespace, *(str(part) for part in parts)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def stable_id(prefix: str, namespace: str, *parts: object, length: int = 20) -> str:
    return f"{prefix}_{stable_hex(namespace, *parts, length=length)}"


def stable_int_seed(master_seed: int, namespace: str, *parts: object) -> int:
    payload = "|".join([str(master_seed), namespace, *(str(part) for part in parts)])
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little", signed=False)
