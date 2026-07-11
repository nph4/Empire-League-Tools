import cmd
import shlex

from empire_tools import espn_client
from empire_tools.auction.state import DraftState, Manager, Player
from empire_tools.auction.suggest import suggest_bid, suggest_targets
from empire_tools.config import load_config


def build_initial_state(config: dict) -> DraftState:
    league = espn_client.get_league(config)
    budget = config["auction"]["budget_per_manager"]
    roster_spots = config["auction"]["roster_spots_per_manager"]

    managers = {
        team.team_name: Manager(name=team.team_name, budget=budget)
        for team in league.teams
    }
    available = {
        player.name: Player(name=player.name, position=player.position, pro_team=player.proTeam)
        for player in league.free_agents(size=2000)
    }
    return DraftState(managers=managers, available=available, roster_spots_per_manager=roster_spots)


class AuctionShell(cmd.Cmd):
    intro = "Empire League auction assistant. Type help or ? for commands."
    prompt = "(auction) "

    def __init__(self, state: DraftState):
        super().__init__()
        self.state = state

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
        """available [POSITION] - list available players, optionally filtered by position"""
        position = arg.strip().upper() or None
        for player in sorted(self.state.available.values(), key=lambda p: p.name):
            if position and player.position != position:
                continue
            print(f"{player.name:<25} {player.position:<4} {player.pro_team}")

    def do_suggest(self, arg):
        """suggest "Player Name" - show a suggested max bid for a player"""
        player_name = arg.strip().strip('"')
        if not player_name:
            print('Usage: suggest "Player Name"')
            return
        try:
            print(suggest_bid(self.state, player_name))
        except NotImplementedError as e:
            print(f"Not implemented yet: {e}")

    def do_targets(self, arg):
        """targets "Manager Name" - show suggested players to target for a manager"""
        manager_name = arg.strip().strip('"')
        if not manager_name:
            print('Usage: targets "Manager Name"')
            return
        try:
            print(suggest_targets(self.state, manager_name))
        except NotImplementedError as e:
            print(f"Not implemented yet: {e}")

    def do_quit(self, arg):
        """quit - exit the auction assistant"""
        return True

    do_exit = do_quit


def main():
    config = load_config()
    state = build_initial_state(config)
    AuctionShell(state).cmdloop()


if __name__ == "__main__":
    main()
