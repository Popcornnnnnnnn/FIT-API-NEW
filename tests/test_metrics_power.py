from app.metrics.activities.power import compute_power_info


def test_compute_power_info_basic():
    stream = {
        'power': [100, 200, 300, 0, None, 250],
        'w_balance': [10.0, 9.0, 8.0, 8.5],
    }
    res = compute_power_info(stream, ftp=250, session_data=None)
    assert res is not None
    assert res['avg_power'] > 0
    assert res['max_power'] == 300
    assert res['normalized_power'] >= res['avg_power']
    assert res['intensity_factor'] is not None
    assert res['work_above_ftp'] >= 0

