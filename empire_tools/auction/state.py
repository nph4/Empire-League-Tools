from dataclasses import dataclass, field


@dataclass
class Manager:
    name: str
    budget: int
    spent: int = 0
    roster_size: int = 0

    @property
    def remaining(self) -> int:
        return self.budget - self.spent


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
    roster_spots_per_manager: int
    history: list[Sale] = field(default_factory=list)

    def max_bid(self, manager_name: str) -> int:
        """Highest a manager can bid: remaining budget, minus $1 reserved
        for each other roster spot they still need to fill."""
        manager = self.managers[manager_name]
        spots_left_after_this_pick = self.roster_spots_per_manager - manager.roster_size - 1
        return manager.remaining - max(spots_left_after_this_pick, 0)

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

        manager.spent += amount
        manager.roster_size += 1
        del self.available[player_name]

        sale = Sale(player=player_name, manager=manager_name, amount=amount)
        self.history.append(sale)
        return sale
