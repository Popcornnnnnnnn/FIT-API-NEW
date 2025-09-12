from app.analyzers.strava.extract import extract_stream_data


def test_extract_velocity_to_speed():
    stream = {
        'time': {'data': [0, 1, 2]},
        'velocity_smooth': {'data': [1.0, 2.0, 3.0], 'series_type': 'time'},  # m/s
    }
    keys = ['velocity_smooth']
    out = extract_stream_data(stream, keys, resolution='high')
    assert out is not None and len(out) == 1
    item = out[0]
    assert item['type'] == 'speed'
    # check conversion to km/h (approx)
    assert item['data'][0] == 3.6

