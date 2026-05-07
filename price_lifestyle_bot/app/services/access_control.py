from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class PairingCode:
    code: str
    user_id: int
    created_at: datetime
    expires_at: datetime


class AccessControlStore:
    def __init__(self, vault_path: str) -> None:
        self.root = Path(vault_path).expanduser() / "security"
        self.allowlist_path = self.root / "allowlist.json"
        self.pairing_path = self.root / "pairing-codes.json"

    def is_allowed(
        self,
        *,
        user_id: int,
        mode: str,
        admin_ids: list[int],
    ) -> bool:
        if mode == "open":
            return True
        if user_id in admin_ids:
            return True
        return user_id in self.allowed_users()

    def allowed_users(self) -> set[int]:
        if not self.allowlist_path.exists():
            return set()
        raw = json.loads(self.allowlist_path.read_text(encoding="utf-8"))
        return {int(item) for item in raw}

    def allow_user(self, user_id: int) -> None:
        users = self.allowed_users()
        users.add(user_id)
        self.root.mkdir(parents=True, exist_ok=True)
        self.allowlist_path.write_text(
            json.dumps(sorted(users), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_pairing_code(
        self,
        *,
        user_id: int,
        now: datetime | None = None,
        ttl_minutes: int = 15,
    ) -> PairingCode:
        current = now or datetime.now(UTC)
        existing = next(
            (item for item in self.list_pairing_codes(now=current) if item.user_id == user_id),
            None,
        )
        if existing is not None:
            return existing
        code = secrets.token_hex(2).upper()
        pairings = self.list_pairing_codes(now=current)
        pairing = PairingCode(
            code=code,
            user_id=user_id,
            created_at=current,
            expires_at=current + timedelta(minutes=ttl_minutes),
        )
        pairings.append(pairing)
        self._write_pairings(pairings)
        return pairing

    def approve_pairing_code(
        self,
        *,
        code: str,
        now: datetime | None = None,
    ) -> int | None:
        current = now or datetime.now(UTC)
        normalized = code.strip().upper()
        pairings = self.list_pairing_codes(now=current)
        approved_user_id: int | None = None
        remaining: list[PairingCode] = []
        for pairing in pairings:
            if pairing.code == normalized:
                approved_user_id = pairing.user_id
                continue
            remaining.append(pairing)
        if approved_user_id is None:
            self._write_pairings(remaining)
            return None
        self.allow_user(approved_user_id)
        self._write_pairings(remaining)
        return approved_user_id

    def list_pairing_codes(self, *, now: datetime | None = None) -> list[PairingCode]:
        current = now or datetime.now(UTC)
        if not self.pairing_path.exists():
            return []
        raw = json.loads(self.pairing_path.read_text(encoding="utf-8"))
        pairings = [
            PairingCode(
                code=str(item["code"]),
                user_id=int(item["user_id"]),
                created_at=datetime.fromisoformat(str(item["created_at"])).astimezone(UTC),
                expires_at=datetime.fromisoformat(str(item["expires_at"])).astimezone(UTC),
            )
            for item in raw
        ]
        active = [pairing for pairing in pairings if pairing.expires_at > current]
        if len(active) != len(pairings):
            self._write_pairings(active)
        return active

    def _write_pairings(self, pairings: list[PairingCode]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.pairing_path.write_text(
            json.dumps(
                [
                    {
                        "code": pairing.code,
                        "user_id": pairing.user_id,
                        "created_at": pairing.created_at.isoformat(),
                        "expires_at": pairing.expires_at.isoformat(),
                    }
                    for pairing in pairings
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
