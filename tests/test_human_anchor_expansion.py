from scripts.expand_human_anchor_from_demo import infer_order_type, normalize_flute, stratified_sample, DemoOrder


def _order(idx, flute, order_type):
    return DemoOrder(
        id=idx,
        product=f"case-{idx}",
        client="demo",
        qty=1000,
        box_l=100,
        box_w=100,
        box_h=100,
        flute_raw=flute,
        flute_norm=normalize_flute(flute),
        order_type=order_type,
        has_lamination=0,
        print_style="demo",
    )


def test_normalize_flute_groups_common_aliases():
    assert normalize_flute("EB瓦") == "EB"
    assert normalize_flute("BC瓦或AB瓦") == "MIXED_AB_BC"
    assert normalize_flute("单E瓦") == "SINGLE_E"
    assert normalize_flute("------") == "UNKNOWN"


def test_infer_order_type_from_demo_text():
    assert infer_order_type("出口纸箱案例") == "export"
    assert infer_order_type("普通纸箱案例") == "domestic_or_unspecified"


def test_stratified_sample_round_robins_buckets():
    orders = []
    idx = 1
    for order_type in ["export", "domestic_or_unspecified"]:
        for flute in ["EB", "BC", "AB"]:
            for _ in range(3):
                orders.append(_order(idx, flute, order_type))
                idx += 1

    selected, metadata = stratified_sample(orders, n=6, seed=1)
    assert len(selected) == 6
    assert set(metadata["selected_order_type"]) == {"export", "domestic_or_unspecified"}
    assert len(metadata["selected_flute"]) >= 3
