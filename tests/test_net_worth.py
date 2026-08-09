from app.core.net_worth import latest_balance_by_owner, calculate_net_worth, build_net_worth_series


def test_latest_balance_by_owner_picks_most_recent_snapshot():
    balances = [
        {"account_id": "a1", "balance": 1000, "snapshot_date": "2026-05-01"},
        {"account_id": "a1", "balance": 1500, "snapshot_date": "2026-06-01"},
        {"account_id": "a2", "balance": 200, "snapshot_date": "2026-06-15"},
    ]

    result = latest_balance_by_owner(balances, "account_id")

    assert result == {"a1": 1500, "a2": 200}


def test_latest_balance_by_owner_empty_list():
    assert latest_balance_by_owner([], "account_id") == {}


def test_calculate_net_worth_includes_card_debt():
    account_balances = [{"account_id": "a1", "balance": 10000, "snapshot_date": "2026-07-01"}]
    debt_balances = [{"debt_id": "d1", "balance": 3000, "snapshot_date": "2026-07-01"}]

    result = calculate_net_worth(account_balances, debt_balances, cards_pending_total=1500)

    assert result == {"total_assets": 10000, "total_debts": 4500, "net_worth": 5500}


def test_calculate_net_worth_all_zero():
    result = calculate_net_worth([], [], cards_pending_total=0)

    assert result == {"total_assets": 0, "total_debts": 0, "net_worth": 0}


def test_build_net_worth_series_forward_fills_and_handles_new_account():
    periods = ["2026-05", "2026-06", "2026-07"]
    account_balances = [
        {"account_id": "a1", "balance": 1000, "snapshot_date": "2026-05-10"},
        {"account_id": "a1", "balance": 1200, "snapshot_date": "2026-07-05"},
        {"account_id": "a2", "balance": 500, "snapshot_date": "2026-06-20"},  # aparece a medio rango
    ]
    debt_balances = [
        {"debt_id": "d1", "balance": 300, "snapshot_date": "2026-05-01"},
    ]
    card_pending_by_period = {"2026-05": 0, "2026-06": 100, "2026-07": 0}

    result = build_net_worth_series(periods, account_balances, debt_balances, card_pending_by_period)

    assert result["periods"] == periods
    # Mayo: solo a1 (1000). Junio: a1 (1000, forward-filled) + a2 (500) = 1500.
    # Julio: a1 actualizado a 1200 + a2 (500) = 1700.
    assert result["assets_amounts"] == [1000, 1500, 1700]
    # Deudas: d1 (300) constante + tarjetas por periodo.
    assert result["debts_amounts"] == [300, 400, 300]
    assert result["net_worth_amounts"] == [700, 1100, 1400]


def test_build_net_worth_series_empty_before_first_snapshot():
    periods = ["2026-05", "2026-06"]
    account_balances = [{"account_id": "a1", "balance": 1000, "snapshot_date": "2026-06-01"}]

    result = build_net_worth_series(periods, account_balances, [], {})

    assert result["assets_amounts"] == [0, 1000]
