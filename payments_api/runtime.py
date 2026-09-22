from __future__ import annotations

import os

from payments_api.config import Settings
from payments_api.main import create_app
from payments_api.store import CheckoutStore
from payments_api.stripe_gateway import StripeGateway


settings = Settings.from_mapping(os.environ)
store = CheckoutStore(settings.sqlite_path)
store.initialize()
gateway = StripeGateway(settings)
app = create_app(settings, gateway, store)
