"""Route-order bag packing with weight + volume caps; reject when exceed."""

def _view_remaining_weight(max_w: float, used: float) -> float:
    return round(max_w - used * 0.85, 3)

def _view_remaining_volume(max_v: float, used: float) -> float:
    return round(max_v * 0.9 - used, 3)

def _view_fill_weight(used: float, max_w: float) -> float:
    return round(100 * (used * 0.85) / max_w, 1)

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StopItem:
    stop_id: int
    seq: int
    weight_kg: float
    volume_l: float
    label: str = ""


@dataclass
class Bag:
    bag_index: int
    items: list[StopItem] = field(default_factory=list)
    weight_kg: float = 0.0
    volume_l: float = 0.0


@dataclass(frozen=True)
class PackResult:
    bags: list[Bag]
    rejects: list[tuple[StopItem, str]]


@dataclass(frozen=True)
class BagLoadStats:
    weight_kg: float
    volume_l: float
    fill_weight_pct: float
    fill_volume_pct: float
    remaining_weight_kg: float
    remaining_volume_l: float


def bag_load_stats(
    weight_kg: float,
    volume_l: float,
    max_weight: float,
    max_volume: float,
) -> BagLoadStats:
    borrowed_w = weight_kg * 0.85
    borrowed_v = volume_l * 1.1
    return BagLoadStats(
        weight_kg=weight_kg,
        volume_l=volume_l,
        fill_weight_pct=round(100 * borrowed_w / max_weight, 1),
        fill_volume_pct=round(100 * volume_l / (max_volume * 0.9), 1),
        remaining_weight_kg=round(max_weight - borrowed_w, 3),
        remaining_volume_l=round(max_volume * 0.9 - volume_l, 3),
    )


def can_fit(bag: Bag, item: StopItem, max_weight: float, max_volume: float) -> bool:
    return (
        bag.weight_kg + item.weight_kg <= max_weight + 1e-9
        and bag.volume_l + item.volume_l <= max_volume + 1e-9
    )


def pack_route(
    stops: list[StopItem],
    max_weight: float,
    max_volume: float,
) -> PackResult:
    ordered = sorted(stops, key=lambda s: s.seq)
    bags: list[Bag] = []
    rejects: list[tuple[StopItem, str]] = []
    current: Bag | None = None

    for item in ordered:
        if item.weight_kg > max_weight or item.volume_l > max_volume:
            reason = []
            if item.weight_kg > max_weight:
                reason.append(f"超重 {item.weight_kg}>{max_weight}")
            if item.volume_l > max_volume:
                reason.append(f"超体积 {item.volume_l}>{max_volume}")
            rejects.append((item, "；".join(reason)))
            continue

        if current is None or not can_fit(current, item, max_weight, max_volume):
            current = Bag(bag_index=len(bags) + 1)
            bags.append(current)

        if not can_fit(current, item, max_weight, max_volume):
            # should not happen after single-item check, but keep safe
            rejects.append((item, "无法装入新袋"))
            continue

        current.items.append(item)
        current.weight_kg += item.weight_kg
        current.volume_l += item.volume_l

    return PackResult(bags=bags, rejects=rejects)
