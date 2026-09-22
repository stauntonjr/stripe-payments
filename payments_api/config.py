from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping
from urllib.parse import urlsplit


_PRICE_ID = re.compile(r"price_[A-Za-z0-9]+")
_INTEGRATION_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*_[a-z]{8}")


@dataclass(frozen=True)
class Settings:
    stripe_secret_key: str
    stripe_webhook_secret: str
    price_id: str
    integration_identifier: str
    checkout_base_url: str
    sqlite_path: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "Settings":
        required = {
            "STRIPE_SECRET_KEY": "stripe_secret_key",
            "STRIPE_WEBHOOK_SECRET": "stripe_webhook_secret",
            "STRIPE_TICKERPULSE_PRICE_ID": "price_id",
            "STRIPE_INTEGRATION_IDENTIFIER": "integration_identifier",
            "CHECKOUT_BASE_URL": "checkout_base_url",
            "SQLITE_PATH": "sqlite_path",
        }
        parsed: dict[str, str] = {}
        for environment_name, field_name in required.items():
            value = values.get(environment_name)
            if value is None or not value.strip():
                raise ValueError(f"{environment_name} is required")
            parsed[field_name] = value

        if _PRICE_ID.fullmatch(parsed["price_id"]) is None:
            raise ValueError("STRIPE_TICKERPULSE_PRICE_ID must be a Stripe Price ID")

        if _INTEGRATION_IDENTIFIER.fullmatch(parsed["integration_identifier"]) is None:
            raise ValueError(
                "STRIPE_INTEGRATION_IDENTIFIER must end in eight lowercase letters"
            )

        origin = parsed["checkout_base_url"]
        split = urlsplit(origin)
        if (
            split.scheme != "https"
            or not split.hostname
            or split.username is not None
            or split.password is not None
            or split.path not in ("", "/")
            or split.query
            or split.fragment
        ):
            raise ValueError("CHECKOUT_BASE_URL must be a clean HTTPS origin")
        parsed["checkout_base_url"] = origin.rstrip("/")

        return cls(**parsed)
