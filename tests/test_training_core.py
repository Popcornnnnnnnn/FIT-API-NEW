from app.core.analytics.training import (
    aerobic_effect,
    anaerobic_effect,
    power_zone_percentages,
    power_zone_times,
    primary_training_benefit,
    calculate_training_load,
)


def test_training_effects_and_zones():
    # simple synthetic power data around FTP
    ftp = 250
    power = [200]*120 + [260]*120 + [300]*60  # 5 min Z3, 5 min Z4+, 1 min Z5

    ae = aerobic_effect(power, ftp)
    ne = anaerobic_effect(power, ftp)
    assert 0.0 <= ae <= 5.0
    assert 0.0 <= ne <= 4.0

    perc = power_zone_percentages(power, ftp)
    times = power_zone_times(power, ftp)
    assert len(perc) == 7
    assert len(times) == 7

    pb, secondary = primary_training_benefit(perc, times, duration_min=int(len(power)/60), aerobic_effect_val=ae, anaerobic_effect_val=ne, ftp=ftp, max_power=max(power))
    assert isinstance(pb, str)

    # TSS-like training load
    tl = calculate_training_load(avg_power=int(sum(power)/len(power)), ftp=ftp, duration_seconds=len(power))
    assert tl >= 0

