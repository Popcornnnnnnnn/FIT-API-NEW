from app.metrics.activities.altitude import compute_altitude_info


def test_compute_altitude_info_basic():
    stream = {
        'altitude': [10, 12, 15, 14, 20, 25],
        'distance': [0, 50, 120, 200, 260, 320],
    }
    res = compute_altitude_info(stream, session_data=None)
    assert res is not None
    assert res['elevation_gain'] >= 0
    assert 'max_grade' in res
    assert 'uphill_distance' in res and 'downhill_distance' in res

