"""Editable settings. Loads the original compiled settings (settings_legacy.pyc,
an unchanged copy of the old settings.pyc), then applies overrides below."""
from .settings_legacy import *  # noqa: F401,F403

# --- Homepage v5: Agrovet opens first. Set HOME_V5 = False to bring back the old homepage ---
HOME_V5 = True
if "MIDDLEWARE" in globals() and "shop.home_v5.HomeV5Middleware" not in MIDDLEWARE:
    MIDDLEWARE = list(MIDDLEWARE) + ["shop.home_v5.HomeV5Middleware"]
