import os
import json
import datetime
from typing import Dict, Set, List, Optional, Iterable, Tuple

try:
    from fitparse import FitFile
    from fitparse.utils import FitParseError
except ImportError as exc:
    raise SystemExit(
        "fitparse 未安装。请先执行: pip install fitparse"
    ) from exc

try:
    import fitdecode
except ImportError:
    fitdecode = None  # type: ignore[assignment]


ABS_FITS_DIR = "/Users/popcornnnnnn/Code/Work/Test/Fits"


def _to_jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime.datetime):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    try:
        return str(value)
    except Exception:
        return repr(value)


def _update_fields_from_message(
    message_name: Optional[str],
    fields: List[object],
    exclude_messages: Set[str],
    message_to_fields: Dict[str, Set[str]],
) -> None:
    if not message_name or message_name in exclude_messages:
        return
    field_names: Set[str] = message_to_fields.setdefault(message_name, set())
    for field in fields:
        fname = getattr(field, "name", None)
        if fname:
            field_names.add(fname)


def _collect_fields_with_fitdecode(
    filepath: str,
    exclude_messages: Set[str],
    message_to_fields: Dict[str, Set[str]],
) -> bool:
    if fitdecode is None:
        return False
    try:
        with fitdecode.FitReader(
            filepath,
            check_crc=fitdecode.CrcCheck.DISABLED,
            error_handling=fitdecode.ErrorHandling.IGNORE,
        ) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitDataMessage):
                    _update_fields_from_message(
                        getattr(frame, "name", None),
                        list(getattr(frame, "fields", [])),
                        exclude_messages,
                        message_to_fields,
                    )
        return True
    except Exception as exc:
        print(f"fitdecode 解析失败: {filepath} -> {exc}")
        return False


def _collect_laps_with_fitparse(
    fit: FitFile,
) -> List[List[dict]]:
    laps: List[List[dict]] = []
    for message in fit.get_messages("lap"):
        fields_list: List[dict] = []
        for field in message.fields:
            fname = getattr(field, "name", None)
            if not fname:
                continue
            fval = getattr(field, "value", None)
            funits = getattr(field, "units", None)
            fields_list.append({
                "name": fname,
                "value": fval,
                "units": funits,
            })
        laps.append(fields_list)
    return laps


def _collect_laps_with_fitdecode(filepath: str) -> List[List[dict]]:
    if fitdecode is None:
        raise SystemExit(
            "fitparse 无法解析该文件，且未安装 fitdecode，无法继续处理。"
        )
    try:
        with fitdecode.FitReader(
            filepath,
            check_crc=fitdecode.CrcCheck.DISABLED,
            error_handling=fitdecode.ErrorHandling.IGNORE,
        ) as reader:
            laps: List[List[dict]] = []
            for frame in reader:
                if isinstance(frame, fitdecode.FitDataMessage) and getattr(frame, "name", None) == "lap":
                    fields_list: List[dict] = []
                    for field in getattr(frame, "fields", []):
                        fname = getattr(field, "name", None)
                        if not fname:
                            continue
                        fields_list.append({
                            "name": fname,
                            "value": getattr(field, "value", None),
                            "units": getattr(field, "units", None),
                        })
                    laps.append(fields_list)
        return laps
    except Exception as exc:
        raise SystemExit(f"无法解析 lap 消息: {filepath} -> {exc}")


def _iter_messages_with_fitdecode(filepath: str) -> Iterable[Tuple[Optional[str], List[object]]]:
    if fitdecode is None:
        raise SystemExit(
            "需要安装 fitdecode 以解析包含自定义字段的 FIT 文件。"
        )
    try:
        with fitdecode.FitReader(
            filepath,
            check_crc=fitdecode.CrcCheck.DISABLED,
            error_handling=fitdecode.ErrorHandling.IGNORE,
        ) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitDataMessage):
                    yield getattr(frame, "name", None), list(getattr(frame, "fields", []))
    except Exception as exc:
        raise SystemExit(f"fitdecode 无法解析文件: {filepath} -> {exc}")


def _iter_messages_for_summary(filepath: str) -> Iterable[Tuple[Optional[str], List[object]]]:
    try:
        fit = FitFile(filepath)
    except Exception as exc:
        raise SystemExit(f"无法解析文件: {filepath} -> {exc}")

    try:
        for message in fit.get_messages():
            yield getattr(message, "name", None), list(getattr(message, "fields", []))
        return
    except FitParseError as err:
        if fitdecode is None:
            raise SystemExit(f"无法解析文件: {filepath} -> {err}")
        print(f"fitparse 解析失败，生成概要时改用 fitdecode: {filepath} -> {err}")
        yield from _iter_messages_with_fitdecode(filepath)
    except Exception as exc:
        if fitdecode is None:
            raise SystemExit(f"无法解析文件: {filepath} -> {exc}")
        print(f"fitparse 解析出现异常，生成概要时改用 fitdecode: {filepath} -> {exc}")
        yield from _iter_messages_with_fitdecode(filepath)


def _extract_field_values(
    fields: List[object],
    include_only: Optional[Set[str]] = None,
) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    for field in fields:
        fname = getattr(field, "name", None)
        if not fname:
            continue
        if include_only and fname not in include_only:
            continue
        value = getattr(field, "value", None)
        entry: Dict[str, object] = {"value": _to_jsonable(value)}
        units = getattr(field, "units", None)
        if units:
            entry["units"] = units
        result[fname] = entry
    return result


def _build_summary_payload(
    filepath: str,
    exclude_messages: Optional[Set[str]] = None,
) -> Dict[str, object]:
    if exclude_messages is None:
        exclude_messages = set()

    file_keys = {"type", "manufacturer", "product", "product_name", "time_created"}
    activity_keys = {"timestamp", "local_timestamp", "total_timer_time", "event", "event_type", "num_sessions"}
    event_keys = {"timestamp", "event", "event_type", "event_group", "timer_trigger"}
    lap_keys = {
        "timestamp",
        "start_time",
        "total_timer_time",
        "total_elapsed_time",
        "total_distance",
        "total_calories",
        "avg_speed",
        "enhanced_avg_speed",
        "max_speed",
        "enhanced_max_speed",
        "avg_heart_rate",
        "max_heart_rate",
        "min_heart_rate",
        "avg_power",
        "avg_running_cadence",
        "avg_step_length",
        "avg_vertical_oscillation",
        "avg_vertical_ratio",
        "avg_temperature",
        "avg_stance_time",
        "avg_stance_time_percent",
        "total_ascent",
        "total_descent",
    }

    summary: Dict[str, object] = {
        "file": filepath,
        "file_id": {},
        "activity": {},
        "events": [],
        "laps": [],
        "totals": {},
    }

    total_distance = 0.0
    total_timer_time = 0.0
    total_elapsed_time = 0.0

    for message_name, fields in _iter_messages_for_summary(filepath):
        if not message_name or message_name in exclude_messages:
            continue

        if message_name == "file_id" and not summary["file_id"]:
            summary["file_id"] = _extract_field_values(fields, file_keys)
        elif message_name == "activity" and not summary["activity"]:
            summary["activity"] = _extract_field_values(fields, activity_keys)
        elif message_name == "event":
            events = summary["events"]
            if isinstance(events, list) and len(events) < 5:
                events.append(_extract_field_values(fields, event_keys))
        elif message_name == "lap":
            lap_fields = _extract_field_values(fields, lap_keys)
            lap_entry = {
                "lap_index": len(summary["laps"]),
                "fields": lap_fields,
            }
            summary["laps"].append(lap_entry)

            distance_val = lap_fields.get("total_distance", {}).get("value")
            if isinstance(distance_val, (int, float)):
                total_distance += float(distance_val)
            timer_val = lap_fields.get("total_timer_time", {}).get("value")
            if isinstance(timer_val, (int, float)):
                total_timer_time += float(timer_val)
            elapsed_val = lap_fields.get("total_elapsed_time", {}).get("value")
            if isinstance(elapsed_val, (int, float)):
                total_elapsed_time += float(elapsed_val)

    totals: Dict[str, Dict[str, object]] = {}
    if total_distance:
        totals["total_distance"] = {"value": round(total_distance, 3), "units": "m"}
    if total_timer_time:
        totals["total_timer_time"] = {"value": round(total_timer_time, 3), "units": "s"}
    if total_elapsed_time:
        totals["total_elapsed_time"] = {"value": round(total_elapsed_time, 3), "units": "s"}
    totals["lap_count"] = {"value": len(summary["laps"])}

    summary["totals"] = totals
    return summary


def export_summary(
    filepath: str,
    exclude_messages: Optional[Set[str]] = None,
    out_dir: Optional[str] = None,
) -> str:
    if out_dir is None:
        out_dir = os.path.dirname(__file__)

    payload = _build_summary_payload(filepath, exclude_messages=exclude_messages)
    base = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(out_dir, f"summary_{base}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def list_fit_fields(
    fits_dir: str,
    exclude_messages: Optional[Set[str]] = None,
) -> Dict[str, Set[str]]:
    if exclude_messages is None:
        exclude_messages = set()

    message_to_fields: Dict[str, Set[str]] = {}

    for entry in sorted(os.listdir(fits_dir)):
        if not entry.lower().endswith(".fit"):
            continue
        filepath = os.path.join(fits_dir, entry)

        try:
            fit = FitFile(filepath)
        except Exception as e:
            print(f"跳过无法解析的文件: {filepath} -> {e}")
            continue

        try:
            for message in fit.get_messages():
                _update_fields_from_message(
                    getattr(message, "name", None),
                    list(getattr(message, "fields", [])),
                    exclude_messages,
                    message_to_fields,
                )
        except FitParseError as e:
            if _collect_fields_with_fitdecode(filepath, exclude_messages, message_to_fields):
                print(f"fitparse 解析失败，已改用 fitdecode: {filepath} -> {e}")
            else:
                print(f"跳过包含无效字段定义的文件: {filepath} -> {e}")
            continue

    return message_to_fields


def format_output(message_to_fields: Dict[str, Set[str]]) -> List[str]:
    lines: List[str] = []
    for msg_name in sorted(message_to_fields.keys()):
        fields_sorted = sorted(message_to_fields[msg_name])
        lines.append(f"[{msg_name}] ({len(fields_sorted)} 个字段)")
        for fname in fields_sorted:
            lines.append(f"  - {fname}")
    return lines


def list_single_fit_fields(
    filepath: str,
    exclude_messages: Optional[Set[str]] = None,
) -> Dict[str, Set[str]]:
    if exclude_messages is None:
        exclude_messages = set()

    message_to_fields: Dict[str, Set[str]] = {}

    try:
        fit = FitFile(filepath)
    except Exception as e:
        raise SystemExit(f"无法解析文件: {filepath} -> {e}")

    try:
        for message in fit.get_messages():
            _update_fields_from_message(
                getattr(message, "name", None),
                list(getattr(message, "fields", [])),
                exclude_messages,
                message_to_fields,
            )
    except FitParseError as e:
        if _collect_fields_with_fitdecode(filepath, exclude_messages, message_to_fields):
            print(f"fitparse 解析失败，已改用 fitdecode: {filepath} -> {e}")
        else:
            raise SystemExit(f"无法解析文件: {filepath} -> {e}")

    return message_to_fields


def export_lap_details(filepath: str, out_dir: Optional[str] = None) -> str:
    if out_dir is None:
        out_dir = os.path.dirname(__file__)

    try:
        fit = FitFile(filepath)
    except Exception as e:
        raise SystemExit(f"无法解析文件: {filepath} -> {e}")

    try:
        raw_laps = _collect_laps_with_fitparse(fit)
    except FitParseError as e:
        raw_laps = _collect_laps_with_fitdecode(filepath)
        print(f"fitparse 无法解析 lap，已改用 fitdecode: {filepath} -> {e}")

    base = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(out_dir, f"lap_{base}.json")
    laps: List[dict] = []
    for idx, fields in enumerate(raw_laps):
        fields_list: List[dict] = []
        for field in fields:
            fields_list.append({
                "name": field["name"],
                "value": _to_jsonable(field["value"]),
                "units": field["units"],
            })
        laps.append({
            "lap_index": idx,
            "fields": fields_list,
        })
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "file": filepath,
            "lap_count": len(laps),
            "laps": laps,
        }, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> None:
    exclude = {"record", "session"}  # record 即常说的 stream

    # 优先解析指定文件: 2025-08-03-17-41-39.fit
    target_file = os.path.join(ABS_FITS_DIR, "2025-08-03-17-41-39.fit")
    if os.path.isfile(target_file):
        result = list_single_fit_fields(target_file, exclude_messages=exclude)
        if result:
            lines = format_output(result)
            print(f"文件: {target_file}")
            print(f"共发现 {len(result)} 类消息 (已排除: {', '.join(sorted(exclude))})\n")
            print("\n".join(lines))
        out_json = export_lap_details(target_file)
        print(f"已导出 lap 明细: {out_json}")
        summary_json = export_summary(target_file, exclude_messages=exclude)
        print(f"已导出概要信息: {summary_json}")
        return

    # 针对单个文件: Strava_628_Outdoor.fit
    single_file = os.path.join(ABS_FITS_DIR, "Strava_628_Outdoor.fit")
    if os.path.isfile(single_file):
        result = list_single_fit_fields(single_file, exclude_messages=exclude)
        if not result:
            print("目标文件未解析到除 record/session 外的消息类型。")
            return
        lines = format_output(result)
        print(f"文件: {single_file}")
        print(f"共发现 {len(result)} 类消息 (已排除: {', '.join(sorted(exclude))})\n")
        print("\n".join(lines))
        try:
            out_json = export_lap_details(single_file)
            print(f"已导出 lap 明细: {out_json}")
            summary_json = export_summary(single_file, exclude_messages=exclude)
            print(f"已导出概要信息: {summary_json}")
        except Exception as e:
            print(f"导出 lap 明细失败: {e}")
        return

    # 退化为扫描目录
    if not os.path.isdir(ABS_FITS_DIR):
        raise SystemExit(f"未找到目录: {ABS_FITS_DIR}")
    result = list_fit_fields(ABS_FITS_DIR, exclude_messages=exclude)
    if not result:
        print("未从 FIT 文件中解析到除 record/session 外的消息类型。")
        return
    lines = format_output(result)
    print(f"共发现 {len(result)} 类消息 (已排除: {', '.join(sorted(exclude))})\n")
    print("\n".join(lines))

    fit_files = [
        os.path.join(ABS_FITS_DIR, entry)
        for entry in sorted(os.listdir(ABS_FITS_DIR))
        if entry.lower().endswith(".fit")
    ]
    for filepath in fit_files:
        try:
            summary_json = export_summary(filepath, exclude_messages=exclude)
            print(f"已导出概要信息: {summary_json}")
        except SystemExit as exc:
            print(exc)
        except Exception as exc:  # pragma: no cover
            print(f"导出概要信息失败: {filepath} -> {exc}")


if __name__ == "__main__":
    main()
