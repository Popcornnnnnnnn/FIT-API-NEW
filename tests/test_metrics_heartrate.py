from app.metrics.activities.heartrate import compute_heartrate_info


def test_compute_heartrate_info_basic():
    stream = {
        'heart_rate': [100, 110, 115, 120, 118, None, 119],
        'power': [150, 160, 170, 180, 175, 0, 165],
    }
    res = compute_heartrate_info(stream, power_data_present=True, session_data=None)
    assert res is not None
    assert res['avg_heartrate'] >= 100
    assert res['max_heartrate'] >= res['avg_heartrate']
    # lag/decoupling may be None depending on sequence; ensure keys exist
    assert 'heartrate_lag' in res
    assert 'decoupling_rate' in res

