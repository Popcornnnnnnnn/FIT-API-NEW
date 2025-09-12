from app.analyzers.strava.upsampling import is_low_resolution, prepare_for_upsampling, upsample_low_resolution


def test_is_low_resolution_true():
    stream = {'time': {'data': [0, 10, 20, 30]}}
    assert is_low_resolution(stream) is True


def test_is_low_resolution_false():
    stream = {'time': {'data': [0, 1, 2, 3]}}
    assert is_low_resolution(stream) is False


def test_upsample_low_resolution_basic():
    stream = {
        'time': {'data': [0, 10, 20]},
        'watts': {'data': [100, 200, 300]},
    }
    prepared = prepare_for_upsampling(stream)
    up = upsample_low_resolution(prepared, moving_time_seconds=5)
    assert 'watts' in up
    assert len(up['watts']['data']) == 6  # moving_time + 1

