"""Route-order bag packing with weight + volume caps; reject when exceed."""

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
    """额度口径统一：剩余 = 上限 - 已装；填充 = 100 * 已装 / 上限。

    已装重量/体积即袋内各订户点重量/体积之和，与袋明细同源，
    不做任何折扣/放大换算。
    """
    return BagLoadStats(
        weight_kg=weight_kg,
        volume_l=volume_l,
        fill_weight_pct=round(100 * weight_kg / max_weight, 1),
        fill_volume_pct=round(100 * volume_l / max_volume, 1),
        remaining_weight_kg=round(max_weight - weight_kg, 3),
        remaining_volume_l=round(max_volume - volume_l, 3),
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
