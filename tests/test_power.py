from app.core.analytics.power import normalized_power, work_above_ftp, w_balance_decline


def test_normalized_power_basic():
    # constant power should equal itself
    powers = [200] * 120
    assert 195 <= normalized_power(powers) <= 205


def test_work_above_ftp():
    powers = [100, 150, 300, 310, 250]
    assert work_above_ftp(powers, 250) == int(((300-250)+(310-250))/1000)


def test_w_balance_decline():
    arr = [10.0, 8.0, 7.5, 9.0, 7.0]
    assert w_balance_decline(arr) == 3.0

