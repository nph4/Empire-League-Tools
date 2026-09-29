"""Thin wrapper around espn_api for this league.

The league is configured as "open" (public), so no espn_s2/SWID auth
cookies are required to read rosters, free agents, or draft results.

TLS verification goes through the OS certificate store (`truststore`)
rather than requests' bundled certifi CAs, so networks that re-sign HTTPS
traffic (e.g. Zscaler) work as long as the OS trusts their root.
"""

import truststore
from espn_api.football import League

from empire_tools.config import load_config


def get_league(config: dict | None = None) -> League:
    truststore.inject_into_ssl()
    config = config or load_config()
    return League(league_id=config["league_id"], year=config["year"])
