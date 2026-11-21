from scripts.gol_metrics import GOLD_SQL


def test_gold_transform_uses_window_lag_and_rolling_windows():
    assert "LAG(close)" in GOLD_SQL
    assert "ROWS BETWEEN 6 PRECEDING" in GOLD_SQL
    assert "ROWS BETWEEN 29 PRECEDING" in GOLD_SQL


def test_gold_transform_is_idempotent():
    assert "ON CONFLICT (date, ticker) DO UPDATE" in GOLD_SQL


def test_gold_transform_reads_silver():
    assert "FROM silver.stock_clean" in GOLD_SQL
