"""Thin wrapper around espn_api for this league.

The league is configured as "open" (public), so no espn_s2/SWID auth
cookies are required to read rosters, free agents, or draft results.
"""

from espn_api.football import League

from empire_tools.config import load_config


def get_league(config: dict | None = None) -> League:
    config = config or load_config()
    return League(league_id=config["league_id"], year=config["year"])
