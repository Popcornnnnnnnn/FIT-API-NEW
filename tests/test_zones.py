from app.core.analytics.zones import analyze_power_zones, analyze_heartrate_zones


def test_analyze_power_zones_simple():
    zones = analyze_power_zones([100, 150, 200, 250, 300], ftp=200)
    assert isinstance(zones, list)
    assert len(zones) == 7


def test_analyze_heartrate_zones_simple():
    zones = analyze_heartrate_zones([100, 120, 140, 160, 180], max_hr=200)
    assert isinstance(zones, list)
    assert len(zones) == 5

