"""授权码与访问令牌的内存存储(单进程 mock 认证中心)。"""

import secrets
import time
from dataclasses import dataclass

CODE_TTL_SECONDS = 300
TOKEN_TTL_SECONDS = 3600


@dataclass
class CodeEntry:
    user: dict
    client_id: str
    redirect_uri: str
    expires_at: float


class CodeStore:
    def __init__(self) -> None:
        self._codes: dict[str, CodeEntry] = {}

    def issue(self, user: dict, client_id: str, redirect_uri: str) -> str:
        code = secrets.token_urlsafe(24)
        self._codes[code] = CodeEntry(
            user=user, client_id=client_id, redirect_uri=redirect_uri,
            expires_at=time.time() + CODE_TTL_SECONDS,
        )
        return code

    def consume(self, code: str, client_id: str, redirect_uri: str) -> dict | None:
        entry = self._codes.pop(code, None)
        if entry is None or entry.expires_at < time.time():
            return None
        if entry.client_id != client_id or entry.redirect_uri != redirect_uri:
            return None
        return entry.user


class TokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, tuple[dict, float]] = {}

    def issue(self, user: dict) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = (user, time.time() + TOKEN_TTL_SECONDS)
        return token, TOKEN_TTL_SECONDS

    def get(self, token: str) -> dict | None:
        item = self._tokens.get(token)
        if item is None or item[1] < time.time():
            return None
        return item[0]


code_store = CodeStore()
token_store = TokenStore()
