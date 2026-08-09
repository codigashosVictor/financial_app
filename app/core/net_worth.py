def latest_balance_by_owner(balances: list, owner_key: str) -> dict:
    """
    De una lista de snapshots {owner_key: id, balance, snapshot_date},
    regresa {owner_id: balance} tomando el snapshot_date más reciente
    por owner. En empate de fecha, se queda con el último visto.
    """
    latest = {}
    for row in balances:
        owner_id = row[owner_key]
        current = latest.get(owner_id)
        if current is None or row["snapshot_date"] >= current["snapshot_date"]:
            latest[owner_id] = row
    return {owner_id: row["balance"] for owner_id, row in latest.items()}


def calculate_net_worth(account_balances: list, debt_balances: list, cards_pending_total: float) -> dict:
    """
    account_balances / debt_balances: filas crudas de account_balances/debt_balances
    (se toma el último snapshot por cuenta/deuda).
    cards_pending_total: saldo pendiente actual de tarjetas de crédito (ya calculado
    en otro lado con calculate_pending_balance), se suma a las deudas.
    """
    total_assets = round(sum(latest_balance_by_owner(account_balances, "account_id").values()), 2)
    total_debts = round(
        sum(latest_balance_by_owner(debt_balances, "debt_id").values()) + cards_pending_total, 2
    )
    return {
        "total_assets": total_assets,
        "total_debts": total_debts,
        "net_worth": round(total_assets - total_debts, 2),
    }


def build_net_worth_series(
    periods: list,
    account_balance_rows: list,
    debt_balance_rows: list,
    card_pending_by_period: dict,
) -> dict:
    """
    Serie mensual de patrimonio neto con forward-fill: cada cuenta/deuda
    conserva su último saldo conocido hasta que aparece uno nuevo; antes
    de su primer snapshot, contribuye 0 (aún no existía).

    card_pending_by_period: {period: total_pendiente_de_tarjetas_ese_periodo}
    """
    def by_period_and_owner(rows: list, owner_key: str) -> dict:
        """{period: {owner_id: balance}} usando el último snapshot <= fin de ese periodo."""
        sorted_rows = sorted(rows, key=lambda r: r["snapshot_date"])
        result = {}
        running = {}
        row_idx = 0
        for period in periods:
            while row_idx < len(sorted_rows) and sorted_rows[row_idx]["snapshot_date"][:7] <= period:
                row = sorted_rows[row_idx]
                running[row[owner_key]] = row["balance"]
                row_idx += 1
            result[period] = dict(running)
        return result

    assets_by_period = by_period_and_owner(account_balance_rows, "account_id")
    debts_by_period = by_period_and_owner(debt_balance_rows, "debt_id")

    assets_amounts = [round(sum(assets_by_period[p].values()), 2) for p in periods]
    debts_amounts = [
        round(sum(debts_by_period[p].values()) + card_pending_by_period.get(p, 0), 2) for p in periods
    ]
    net_worth_amounts = [round(a - d, 2) for a, d in zip(assets_amounts, debts_amounts)]

    return {
        "periods": periods,
        "assets_amounts": assets_amounts,
        "debts_amounts": debts_amounts,
        "net_worth_amounts": net_worth_amounts,
    }
