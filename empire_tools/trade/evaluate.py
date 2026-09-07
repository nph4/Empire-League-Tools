"""Proposed-trade grading: pure logic, no ESPN or I/O dependency (so it's
directly unit-testable, like `auction/state.py` and `auction/suggest.py`).

Every trade is graded from both sides and on two independent value models:

* **Rest-of-season (ROS)** - driven by ESPN season-point projections. A
  dynasty ranking is the wrong ruler for "who helps me win *now*", so this
  model uses projected points, not the dynasty value pool.
* **Long-term** - driven by the shared dynasty value pool
  (`valuations.build_value_pool_from_config`). A plain value-in vs
  value-out comparison on that pool: no aging curve, no contention-window
  overlay.

Each model turns into a letter via a symmetric "fairness score",
``(value_in - value_out) / max(value_in, value_out)`` from the graded
side's point of view, mapped through `GRADE_BANDS`. The score is
antisymmetric between the two sides in the raw (need-agnostic) model - one
side's `in` is the other's `out` over the same denominator - so a lopsided
deal grades A for one team and F for the other.

Positional need is a *soft* nudge on the ROS grade only. Each moving
player's projected-points value is scaled by how strong that side's corps
is at their position *relative to the rest of the league* (see
`strength.model`): a received player at a below-average spot is scaled up
toward `need_boost`, one at a position of strength down toward
`depth_discount` - a continuous version of the old
`faab.bench_only_discount` idea. Given players are scaled the same way off
the *post-trade* roster (leaving a weak spot weaker costs more). When the
league-relative signal is unavailable (deep preseason, all projections 0),
`SideNeeds` carries empty weakness maps and the nudge falls back to a
binary "fills/opens an unfilled starting slot" multiplier. Either way the
nudge is clamped by `need_swing_cap` so it can never move the fairness
score by more than that much - about one grade band - whatever the
multipliers are; `raw_grade` (pre-need) is surfaced alongside `grade` so
the effect stays visible. Long-term deliberately ignores need: dynasty
value is a multi-year price and the roster shape will change.
"""

from dataclasses import dataclass, field
from typing import Callable, Iterable

# Signed fairness score from the graded side's POV (s > 0 => this side comes
# out ahead). Scanned high-to-low; the first band whose lower bound the score
# clears wins. Deliberately generous - dynasty values are noisy - and mirrored
# about 0 so the two sides' raw letters roughly invert. Tuned only by editing
# this list (and the pinned band-edge values in tests/test_trade_evaluate.py).
GRADE_BANDS: list[tuple[float, str]] = [
    (0.35, "A"),
    (0.20, "B+"),
    (0.10, "B"),
    (0.04, "B-"),
    (-0.04, "C"),
    (-0.10, "C-"),
    (-0.20, "D"),
    (-0.35, "D-"),
]  # score below every lower bound => "F"

DEFAULT_NEED_BOOST = 1.10
DEFAULT_DEPTH_DISCOUNT = 0.90
# Hard clamp on |need_score - raw_score| in fairness-score space - roughly
# one grade band. The need nudge stays a tie-breaker, never the grade, no
# matter how boost/discount are configured. In letter terms it's usually a
# one-step move and at most two across a narrow +/- boundary.
DEFAULT_NEED_SWING_CAP = 0.10

_EPS = 1e-9


@dataclass(frozen=True)
class SidePlayer:
    """One player moving in a trade. `ros_value` is ESPN
    `projected_total_points`; `lt_value` is the dynasty value-pool lookup."""

    name: str
    position: str
    ros_value: float
    lt_value: float


@dataclass(frozen=True)
class TradeConfig:
    need_boost: float = DEFAULT_NEED_BOOST
    depth_discount: float = DEFAULT_DEPTH_DISCOUNT
    need_swing_cap: float = DEFAULT_NEED_SWING_CAP


@dataclass(frozen=True)
class SideNeeds:
    """A team's roster-need picture around the trade. `need_before` /
    `need_after` are `roster.needed_positions()` on the current vs the
    hypothetical post-trade roster. `roster_capacity` is
    `RosterRequirements.total_spots` (excludes IR).

    `weakness_before` / `weakness_after` are the ROS-only continuous need
    nudge: `position -> multiplier` (in `[depth_discount, need_boost]`) from
    `strength.model.team_weakness_multipliers` on the current vs post-trade
    roster, measured against the rest of the league. When set they supersede
    the binary `need_before` / `need_after` model for the *grade* multiplier;
    when empty the grade falls back to that binary model. The callouts always
    use the binary sets. Long-term never consults either map."""

    need_before: frozenset[str] = frozenset()
    need_after: frozenset[str] = frozenset()
    roster_size_before: int = 0
    roster_size_after: int = 0
    bench_spots: int = 0
    roster_capacity: int = 0
    weakness_before: dict[str, float] = field(default_factory=dict)  # gates RECEIVED players
    weakness_after: dict[str, float] = field(default_factory=dict)  # gates GIVEN players


@dataclass
class ModelGrade:
    model: str  # "ROS" | "Long-term"
    raw_value_in: float
    raw_value_out: float
    value_in: float  # need-adjusted for ROS; == raw for Long-term
    value_out: float
    raw_score: float  # need-agnostic fairness score
    score: float  # need-adjusted, clamped
    grade: str  # letter off `score`
    raw_grade: str  # letter off `raw_score` - shows what need did


@dataclass
class SideEvaluation:
    team_name: str
    ros: ModelGrade
    long_term: ModelGrade
    callouts: list[str] = field(default_factory=list)


@dataclass
class TradeEvaluation:
    user: SideEvaluation
    counterparty: SideEvaluation


def fairness_score(value_in: float, value_out: float) -> float:
    """``(in - out) / max(in, out, eps)``. Range ~(-1, 1); 0 == perfectly
    even. Antisymmetric between the two trade sides in the raw model,
    because one side's `in` is the other's `out` and the denominator is the
    shared larger total."""
    return (value_in - value_out) / max(value_in, value_out, _EPS)


def score_to_grade(score: float) -> str:
    for lower_bound, letter in GRADE_BANDS:
        if score >= lower_bound:
            return letter
    return "F"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _need_multiplier(fills_or_vacates_starting_slot: bool, cfg: TradeConfig) -> float:
    return cfg.need_boost if fills_or_vacates_starting_slot else cfg.depth_discount


def _need_multiplier_for(
    position: str, need_set: frozenset[str], weakness_map: dict[str, float], cfg: TradeConfig
) -> float:
    """Continuous league-relative multiplier when `weakness_map` is
    populated (positions it didn't score are neutral 1.0); otherwise the
    binary in-`need_set` / not multiplier."""
    if weakness_map:
        return weakness_map.get(position, 1.0)
    return _need_multiplier(position in need_set, cfg)


def grade_side_model(
    model: str,
    received: Iterable[SidePlayer],
    given: Iterable[SidePlayer],
    needs: SideNeeds,
    cfg: TradeConfig,
    *,
    apply_need: bool,
    value_of: Callable[[SidePlayer], float],
) -> ModelGrade:
    received = list(received)
    given = list(given)

    raw_in = sum(value_of(p) for p in received)
    raw_out = sum(value_of(p) for p in given)

    if apply_need:
        # A received player whose position is a current hole fills a slot ->
        # boost. A given player whose position is a hole *after* the trade
        # leaves this side thin there -> boost (losing them costs more).
        # Everything else is bench depth -> discount.
        adj_in = sum(
            value_of(p)
            * _need_multiplier_for(p.position, needs.need_before, needs.weakness_before, cfg)
            for p in received
        )
        adj_out = sum(
            value_of(p)
            * _need_multiplier_for(p.position, needs.need_after, needs.weakness_after, cfg)
            for p in given
        )
    else:
        adj_in, adj_out = raw_in, raw_out

    raw_score = fairness_score(raw_in, raw_out)
    need_score = fairness_score(adj_in, adj_out)
    shift = _clamp(need_score - raw_score, -cfg.need_swing_cap, cfg.need_swing_cap)
    score = raw_score + shift

    return ModelGrade(
        model=model,
        raw_value_in=raw_in,
        raw_value_out=raw_out,
        value_in=adj_in,
        value_out=adj_out,
        raw_score=raw_score,
        score=score,
        grade=score_to_grade(score),
        raw_grade=score_to_grade(raw_score),
    )


def side_callouts(
    received: Iterable[SidePlayer],
    given: Iterable[SidePlayer],
    needs: SideNeeds,
    ros: ModelGrade,
    long_term: ModelGrade,
) -> list[str]:
    received = list(received)
    given = list(given)
    received_positions = {p.position for p in received}
    given_positions = {p.position for p in given}

    lines: list[str] = []

    for position in sorted((needs.need_before - needs.need_after) & received_positions):
        lines.append(f"✓ fills your {position} need")

    for position in sorted((needs.need_after - needs.need_before) & given_positions):
        lines.append(f"⚠ opens a hole at {position}")

    still_short = needs.need_before & needs.need_after & received_positions
    for position in sorted(still_short - (needs.need_before - needs.need_after)):
        lines.append(f"~ adds {position} depth, but a starting hole remains")

    delta = needs.roster_size_after - needs.roster_size_before
    if delta > 0 and needs.roster_size_after > needs.roster_capacity:
        lines.append(
            f"⚠ +{delta} roster spots — over the {needs.roster_capacity}-man "
            f"limit, you'd have to cut someone"
        )
    elif delta < 0:
        lines.append(f"note: {delta} roster spots — frees bench flexibility")

    lines.append(f"net ROS points: {ros.raw_value_in - ros.raw_value_out:+.1f}")
    lines.append(f"net long-term value: {long_term.raw_value_in - long_term.raw_value_out:+.1f}")

    return lines


def evaluate_side(
    team_name: str,
    received: Iterable[SidePlayer],
    given: Iterable[SidePlayer],
    needs: SideNeeds,
    cfg: TradeConfig,
) -> SideEvaluation:
    received = list(received)
    given = list(given)

    ros = grade_side_model(
        "ROS", received, given, needs, cfg, apply_need=True, value_of=lambda p: p.ros_value
    )
    long_term = grade_side_model(
        "Long-term", received, given, needs, cfg, apply_need=False, value_of=lambda p: p.lt_value
    )
    callouts = side_callouts(received, given, needs, ros, long_term)
    return SideEvaluation(team_name=team_name, ros=ros, long_term=long_term, callouts=callouts)


def evaluate_trade(
    user_team_name: str,
    counterparty_team_name: str,
    user_received: Iterable[SidePlayer],
    user_given: Iterable[SidePlayer],
    user_needs: SideNeeds,
    counterparty_needs: SideNeeds,
    cfg: TradeConfig = TradeConfig(),
) -> TradeEvaluation:
    """Grade a proposed trade from both sides. `user_received` /
    `user_given` are the players moving, from the user's point of view; the
    counterparty simply receives what the user gives and vice versa."""
    user_received = list(user_received)
    user_given = list(user_given)

    user = evaluate_side(user_team_name, user_received, user_given, user_needs, cfg)
    counterparty = evaluate_side(
        counterparty_team_name, user_given, user_received, counterparty_needs, cfg
    )
    return TradeEvaluation(user=user, counterparty=counterparty)
