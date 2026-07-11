from dataclasses import dataclass, field

from empire_tools.roster import RosterRequirements


@dataclass
class Manager:
    name: str
    budget: int
    spent: int = 0
    roster_size: int = 0
    starters_remaining: dict[str, int] = field(default_factory=dict)
    flex_remaining: int = 0
    bench_remaining: int = 0

    @property
    def remaining(self) -> int:
        return self.budget - self.spent

    @classmethod
    def new(cls, name: str, budget: int, requirements: RosterRequirements) -> "Manager":
        return cls(
            name=name,
            budget=budget,
            starters_remaining=dict(requirements.starters),
            flex_remaining=requirements.flex_spots,
            bench_remaining=requirements.bench_spots,
        )


@dataclass
class Player:
    name: str
    position: str
    pro_team: str


@dataclass
class Sale:
    player: str
    manager: str
    amount: int


@dataclass
class DraftState:
    managers: dict[str, Manager]
    available: dict[str, Player]
    requirements: RosterRequirements
    history: list[Sale] = field(default_factory=list)

    @property
    def roster_spots_per_manager(self) -> int:
        return self.requirements.total_spots

    def max_bid(self, manager_name: str) -> int:
        """Highest a manager can bid: remaining budget, minus $1 reserved
        for each other roster spot they still need to fill."""
        manager = self.managers[manager_name]
        spots_left_after_this_pick = self.roster_spots_per_manager - manager.roster_size - 1
        return manager.remaining - max(spots_left_after_this_pick, 0)

    def needed_positions(self, manager_name: str) -> set[str]:
        """Positions that would fill a starting (non-bench) slot for this
        manager if drafted right now."""
        manager = self.managers[manager_name]
        needed = {pos for pos, left in manager.starters_remaining.items() if left > 0}
        if manager.flex_remaining > 0:
            needed |= self.requirements.flex_eligible
        return needed

    def _fill_slot(self, manager: Manager, position: str) -> None:
        """Greedily assign a drafted player to the most specific open slot:
        their exact starter position, then a flex spot, then the bench."""
        if manager.starters_remaining.get(position, 0) > 0:
            manager.starters_remaining[position] -= 1
        elif position in self.requirements.flex_eligible and manager.flex_remaining > 0:
            manager.flex_remaining -= 1
        elif manager.bench_remaining > 0:
            manager.bench_remaining -= 1
        # else: roster already full for this manager - shouldn't happen if
        # budgets/roster sizes are configured consistently with `requirements`.

    def record_sale(self, player_name: str, manager_name: str, amount: int) -> Sale:
        if player_name not in self.available:
            raise KeyError(f"{player_name!r} is not in the available player pool")
        if manager_name not in self.managers:
            raise KeyError(f"{manager_name!r} is not a known manager")

        manager = self.managers[manager_name]
        if amount > manager.remaining:
            raise ValueError(
                f"{manager_name} only has {manager.remaining} remaining, cannot spend {amount}"
            )

        player = self.available[player_name]
        manager.spent += amount
        manager.roster_size += 1
        self._fill_slot(manager, player.position)
        del self.available[player_name]

        sale = Sale(player=player_name, manager=manager_name, amount=amount)
        self.history.append(sale)
        return sale
