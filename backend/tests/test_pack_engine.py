from app.services.pack_engine import StopItem, bag_load_stats, pack_route


def test_packs_in_route_order_splitting_bags():
    stops = [
        StopItem(1, 1, 2.0, 3.0),
        StopItem(2, 2, 2.5, 3.0),
        StopItem(3, 3, 1.0, 1.0),
    ]
    result = pack_route(stops, max_weight=4.0, max_volume=10.0)
    assert len(result.bags) == 2
    assert [i.stop_id for i in result.bags[0].items] == [1]
    assert [i.stop_id for i in result.bags[1].items] == [2, 3]
    assert not result.rejects


def test_reject_oversized_stop():
    stops = [StopItem(1, 1, 9.0, 1.0, "大件"), StopItem(2, 2, 1.0, 1.0)]
    result = pack_route(stops, max_weight=5.0, max_volume=5.0)
    assert len(result.rejects) == 1
    assert result.rejects[0][0].stop_id == 1
    assert len(result.bags) == 1
    assert result.bags[0].items[0].stop_id == 2


def test_volume_cap_triggers_new_bag():
    stops = [StopItem(1, 1, 1.0, 4.0), StopItem(2, 2, 1.0, 4.0)]
    result = pack_route(stops, max_weight=10.0, max_volume=5.0)
    assert len(result.bags) == 2


def test_bag_load_stats_remaining_and_fill_pct():
    stats = bag_load_stats(5.7, 8.5, max_weight=8.0, max_volume=18.0)
    assert stats.remaining_weight_kg == 2.3
    assert stats.remaining_volume_l == 9.5
    assert stats.fill_weight_pct == 71.2
    assert stats.fill_volume_pct == 47.2


def test_bag_load_stats_empty_and_full_bag():
    empty = bag_load_stats(0.0, 0.0, max_weight=8.0, max_volume=18.0)
    assert (empty.fill_weight_pct, empty.fill_volume_pct) == (0.0, 0.0)
    assert (empty.remaining_weight_kg, empty.remaining_volume_l) == (8.0, 18.0)

    full = bag_load_stats(8.0, 18.0, max_weight=8.0, max_volume=18.0)
    assert (full.fill_weight_pct, full.fill_volume_pct) == (100.0, 100.0)
    assert (full.remaining_weight_kg, full.remaining_volume_l) == (0.0, 0.0)


def test_packed_bags_reconcile_with_route_limits():
    stops = [
        StopItem(1, 1, 2.0, 3.0),
        StopItem(2, 2, 2.5, 3.0),
        StopItem(3, 3, 1.0, 1.0),
    ]
    max_weight, max_volume = 4.0, 10.0
    result = pack_route(stops, max_weight=max_weight, max_volume=max_volume)
    assert len(result.bags) == 2

    for bag in result.bags:
        # 袋重 == 袋明细已装合计
        assert bag.weight_kg == sum(i.weight_kg for i in bag.items)
        assert bag.volume_l == sum(i.volume_l for i in bag.items)
        stats = bag_load_stats(bag.weight_kg, bag.volume_l, max_weight, max_volume)
        # 剩余额度 == 路线上限 - 本袋已装，三处对账一致
        assert stats.remaining_weight_kg + bag.weight_kg == max_weight
        assert stats.remaining_volume_l + bag.volume_l == max_volume

    by_index = {b.bag_index: b for b in result.bags}
    s1 = bag_load_stats(by_index[1].weight_kg, by_index[1].volume_l, max_weight, max_volume)
    assert (s1.fill_weight_pct, s1.fill_volume_pct) == (50.0, 30.0)
    assert (s1.remaining_weight_kg, s1.remaining_volume_l) == (2.0, 7.0)
    s2 = bag_load_stats(by_index[2].weight_kg, by_index[2].volume_l, max_weight, max_volume)
    assert (s2.fill_weight_pct, s2.fill_volume_pct) == (87.5, 40.0)
    assert (s2.remaining_weight_kg, s2.remaining_volume_l) == (0.5, 6.0)
