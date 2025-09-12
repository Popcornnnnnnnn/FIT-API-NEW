from app.metrics.activities.speed import compute_speed_info


def test_compute_speed_info_with_coasting():
    stream = {
        'speed': [0.5, 5.0, 0.8, 10.0],  # km/h
        'power': [0, 200, 0, 180],
        'elapsed_time': [0, 1, 2, 3],
        'timestamp': [0, 1, 2, 3],
    }
    res = compute_speed_info(stream, session_data=None)
    assert res is not None
    assert res['avg_speed'] > 0
    assert res['coasting_time'] is not None

