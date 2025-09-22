from .test_interval_detection import run_interval_detection_for_all_fixtures

for name, detection, preview in run_interval_detection_for_all_fixtures(
        ftp=260, lthr=170, hr_max=190):
    print(name, detection, preview)


