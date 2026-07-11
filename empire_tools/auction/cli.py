import cmd
import shlex

from empire_tools import espn_client
from empire_tools.auction.state import (
    DraftState,
    Manager,
    Player,
    requirements_from_espn_slot_counts,
)
from empire_tools.auction.suggest import suggest_bid, suggest_targets
from empire_tools.auction.valuations import build_value_pool, load_csv_values
from empire_tools.config import load_config


def build_initial_state(
    config: dict, teams: list, free_agents: list, position_slot_counts: dict[str, int]
) -> DraftState:
    budget = config["auction"]["budget_per_manager"]
    requirements = requirements_from_espn_slot_counts(position_slot_counts)

    managers = {
        team.team_name: Manager.new(team.team_name, budget, requirements) for team in teams
    }
    available = {
        player.name: Player(name=player.name, position=player.position, pro_team=player.proTeam)
        for player in free_agents
    }
    return DraftState(managers=managers, available=available, requirements=requirements)


def build_value_pool_from_config(config: dict, free_agents: list) -> dict[str, float]:
    csv_path = config["auction"].get("values_csv")
    csv_values = load_csv_values(csv_path) if csv_path else {}
    return build_value_pool(csv_values, free_agents)


class AuctionShell(cmd.Cmd):
    intro = "Empire League auction assistant. Type help or ? for commands."
    prompt = "(auction) "

    def __init__(self, state: DraftState, value_pool: dict[str, float]):
        super().__init__()
        self.state = state
        self.value_pool = value_pool

    def do_sold(self, arg):
        """sold "Player Name" AMOUNT "Manager Name" - record a completed sale"""
        try:
            player_name, amount, manager_name = shlex.split(arg)
        except ValueError:
            print('Usage: sold "Player Name" AMOUNT "Manager Name"')
            return
        try:
            sale = self.state.record_sale(player_name, manager_name, int(amount))
        except (KeyError, ValueError) as e:
            print(f"Error: {e}")
            return
        print(f"Recorded: {sale.manager} won {sale.player} for {sale.amount}")

    def do_budgets(self, arg):
        """budgets - show remaining budget and max bid for every manager"""
        for name, manager in sorted(self.state.managers.items(), key=lambda kv: -kv[1].remaining):
            max_bid = self.state.max_bid(name)
            print(f"{name:<20} remaining={manager.remaining:<5} max_bid={max_bid:<5} roster={manager.roster_size}")

    def do_available(self, arg):
        """available [POSITION] - list available players (with suggested bid), optionally filtered by position"""
        position = arg.strip().upper() or None
        players = sorted(
            self.state.available.values(),
            key=lambda p: suggest_bid(self.state, self.value_pool, p.name),
            reverse=True,
        )
        for player in players:
            if position and player.position != position:
                continue
            bid = suggest_bid(self.state, self.value_pool, player.name)
            print(f"{player.name:<25} {player.position:<4} {player.pro_team:<4} suggested_bid={bid}")

    def do_suggest(self, arg):
        """suggest "Player Name" - show a suggested max bid for a player"""
        player_name = arg.strip().strip('"')
        if not player_name:
            print('Usage: suggest "Player Name"')
            return
        try:
            print(suggest_bid(self.state, self.value_pool, player_name))
        except KeyError as e:
            print(f"Error: {e}")

    def do_targets(self, arg):
        """targets "Manager Name" - show suggested players to target for a manager, needed positions first"""
        manager_name = arg.strip().strip('"')
        if not manager_name:
            print('Usage: targets "Manager Name"')
            return
        if manager_name not in self.state.managers:
            print(f"Error: {manager_name!r} is not a known manager")
            return
        for player_name, bid, fills_need in suggest_targets(self.state, self.value_pool, manager_name):
            tag = "NEEDED" if fills_need else "bench"
            print(f"{player_name:<25} suggested_bid={bid:<5} {tag}")

    def do_needs(self, arg):
        """needs "Manager Name" - show remaining roster requirements for a manager"""
        manager_name = arg.strip().strip('"')
        if manager_name not in self.state.managers:
            print(f"Error: {manager_name!r} is not a known manager")
            return
        manager = self.state.managers[manager_name]
        for position, required in self.state.requirements.starters.items():
            filled = required - manager.starters_remaining.get(position, 0)
            print(f"{position:<6} {filled}/{required}")
        if self.state.requirements.flex_spots:
            flex_filled = self.state.requirements.flex_spots - manager.flex_remaining
            eligible = "/".join(sorted(self.state.requirements.flex_eligible))
            print(f"FLEX({eligible}) {flex_filled}/{self.state.requirements.flex_spots}")
        bench_filled = self.state.requirements.bench_spots - manager.bench_remaining
        print(f"BENCH  {bench_filled}/{self.state.requirements.bench_spots}")

    def do_quit(self, arg):
        """quit - exit the auction assistant"""
        return True

    do_exit = do_quit


def main():
    config = load_config()
    league = espn_client.get_league(config)
    free_agents = league.free_agents(size=2000)

    state = build_initial_state(config, league.teams, free_agents, league.settings.position_slot_counts)
    value_pool = build_value_pool_from_config(config, free_agents)
    AuctionShell(state, value_pool).cmdloop()


if __name__ == "__main__":
    main()
