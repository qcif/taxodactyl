#!/usr/bin/env python3

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class FileRecord:
	filename: str
	path: Path


def collect_files(root: Path) -> Dict[str, List[FileRecord]]:
	files_by_name: Dict[str, List[FileRecord]] = defaultdict(list)
	for path in root.rglob("*"):
		if path.is_file():
			files_by_name[path.name].append(FileRecord(filename=path.name, path=path))
	return files_by_name


def read_json(path: Path):
	with path.open("r", encoding="utf-8") as handle:
		return json.load(handle)


def canonical_json(data) -> str:
	return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def short_json(data, max_len: int = 80) -> str:
	compact = json.dumps(data, sort_keys=True, ensure_ascii=False)
	if len(compact) > max_len:
		return compact[: max_len - 3] + "..."
	return compact


def list_item_sort_key(item):
	if isinstance(item, dict):
		if {"flag_id", "target", "target_type"}.issubset(item.keys()):
			return (
				0,
				str(item.get("flag_id", "")),
				str(item.get("target", "")),
				str(item.get("target_type", "")),
			)
		return (1, json.dumps(item, sort_keys=True, ensure_ascii=False))
	return (2, json.dumps(item, sort_keys=True, ensure_ascii=False))


def normalize_json_for_compare(data):
	if isinstance(data, dict):
		return {key: normalize_json_for_compare(value) for key, value in sorted(data.items())}
	if isinstance(data, list):
		normalized_items = [normalize_json_for_compare(item) for item in data]
		return sorted(normalized_items, key=list_item_sort_key)
	return data


def collect_differences(left_data, right_data, path: str, diffs: List[Tuple[str, object, object]]) -> None:
	if type(left_data) is not type(right_data):
		diffs.append((path, left_data, right_data))
		return

	if isinstance(left_data, dict):
		keys = sorted(set(left_data.keys()) | set(right_data.keys()))
		for key in keys:
			next_path = f"{path}.{key}"
			left_has = key in left_data
			right_has = key in right_data
			if not left_has:
				diffs.append((next_path, "<missing>", right_data[key]))
			elif not right_has:
				diffs.append((next_path, left_data[key], "<missing>"))
			else:
				collect_differences(left_data[key], right_data[key], next_path, diffs)
		return

	if isinstance(left_data, list):
		max_len = max(len(left_data), len(right_data))
		for index in range(max_len):
			next_path = f"{path}[{index}]"
			left_has = index < len(left_data)
			right_has = index < len(right_data)
			if not left_has:
				diffs.append((next_path, "<missing>", right_data[index]))
			elif not right_has:
				diffs.append((next_path, left_data[index], "<missing>"))
			else:
				collect_differences(left_data[index], right_data[index], next_path, diffs)
		return

	if left_data != right_data:
		diffs.append((path, left_data, right_data))


def extract_record_context(path: str, left_data, right_data) -> str:
	if not (path.startswith("$[") and "]." in path):
		return ""

	try:
		index_str = path[2 : path.index("]")]
		index = int(index_str)
	except (ValueError, IndexError):
		return ""

	left_item = None
	right_item = None
	if isinstance(left_data, list) and index < len(left_data):
		left_item = left_data[index]
	if isinstance(right_data, list) and index < len(right_data):
		right_item = right_data[index]

	item = right_item if isinstance(right_item, dict) else left_item
	if not isinstance(item, dict):
		return ""

	flag_id = short_json(item.get("flag_id", "?"), 40)
	target = short_json(item.get("target", "?"), 60)
	target_type = short_json(item.get("target_type", "?"), 40)
	return f" flag_id={flag_id} target={target} target_type={target_type}"


def extract_record_fields(path: str, left_data, right_data):
	if not (path.startswith("$[") and "]." in path):
		return None

	try:
		index_str = path[2 : path.index("]")]
		index = int(index_str)
	except (ValueError, IndexError):
		return None

	left_item = None
	right_item = None
	if isinstance(left_data, list) and index < len(left_data):
		left_item = left_data[index]
	if isinstance(right_data, list) and index < len(right_data):
		right_item = right_data[index]

	item = right_item if isinstance(right_item, dict) else left_item
	if not isinstance(item, dict):
		return None

	flag_id = item.get("flag_id", "?")
	target = item.get("target", "?")
	target_type = item.get("target_type", "?")
	field = path.split("].", 1)[1] if "]." in path else ""
	return flag_id, target, target_type, field


def one_line_diff_summary(left_data, right_data) -> List[str]:
	def build_index(data):
		if not isinstance(data, list):
			return {}

		index = {}
		for item in data:
			if not isinstance(item, dict):
				continue
			target_type = item.get("target_type")
			if target_type not in {"pmi", "toi"}:
				continue
			flag_id = item.get("flag_id", "?")
			index[(str(flag_id), str(target_type))] = item
		return index

	def build_candidate_index(data):
		if not isinstance(data, list):
			return {}

		index = defaultdict(dict)
		for item in data:
			if not isinstance(item, dict):
				continue
			if item.get("target_type") != "candidate":
				continue

			flag_id = str(item.get("flag_id", "?"))
			target = str(item.get("target", "?"))
			index[flag_id][target] = item

		return dict(index)

	left_index = build_index(left_data)
	right_index = build_index(right_data)

	keys = sorted(set(left_index.keys()) | set(right_index.keys()))
	parts: List[str] = []
	for flag_id, target_type in keys:
		left_item = left_index.get((flag_id, target_type))
		right_item = right_index.get((flag_id, target_type))

		if left_item is None:
			parts.append(
				f"{flag_id} {target_type} TARGET LEFT <missing> RIGHT {short_json(right_item.get('target'))}"
			)
			continue
		if right_item is None:
			parts.append(
				f"{flag_id} {target_type} TARGET LEFT {short_json(left_item.get('target'))} RIGHT <missing>"
			)
			continue

		left_target = left_item.get("target")
		right_target = right_item.get("target")
		if left_target != right_target:
			parts.append(
				f"{flag_id} {target_type} TARGET LEFT {short_json(left_target)} RIGHT {short_json(right_target)}"
			)
			continue

		left_value = left_item.get("value")
		right_value = right_item.get("value")
		if left_value != right_value:
			parts.append(
				f"{flag_id} {short_json(left_target, 60)} {target_type} LEFT {left_value} RIGHT {right_value}"
			)

	left_candidates = build_candidate_index(left_data)
	right_candidates = build_candidate_index(right_data)

	candidate_flag_ids = sorted(set(left_candidates.keys()) | set(right_candidates.keys()))
	for flag_id in candidate_flag_ids:
		left_targets = sorted(left_candidates.get(flag_id, {}).keys())
		right_targets = sorted(right_candidates.get(flag_id, {}).keys())

		if left_targets != right_targets:
			parts.append(
				f"{flag_id} candidate TARGET LEFT {short_json(left_targets, 140)} RIGHT {short_json(right_targets, 140)}"
			)
			continue

		for target in left_targets:
			left_value = left_candidates[flag_id][target].get("value")
			right_value = right_candidates[flag_id][target].get("value")
			if left_value != right_value:
				parts.append(
					f"{flag_id} {short_json(target, 60)} candidate LEFT {left_value} RIGHT {right_value}"
				)

	if parts:
		return parts

	return ["no visible field-level diff"]


def compare_pairs(
	left_root: Path,
	right_root: Path,
	left_files: Dict[str, List[FileRecord]],
	right_files: Dict[str, List[FileRecord]],
) -> Tuple[int, int, int]:
	same = 0
	different = 0
	invalid_json = 0

	common_names = sorted(set(left_files.keys()) & set(right_files.keys()))

	for name in common_names:
		left_list = left_files[name]
		right_list = right_files[name]

		if len(left_list) != 1 or len(right_list) != 1:
			print(f"[SKIP] Ambiguous filename '{name}'")
			print(f"  Left matches ({len(left_list)}):")
			for record in left_list:
				print(f"    - {record.path.relative_to(left_root)}")
			print(f"  Right matches ({len(right_list)}):")
			for record in right_list:
				print(f"    - {record.path.relative_to(right_root)}")
			continue

		left_path = left_list[0].path
		right_path = right_list[0].path

		try:
			left_json = read_json(left_path)
			right_json = read_json(right_path)
		except json.JSONDecodeError as exc:
			invalid_json += 1
			print(f"[INVALID JSON] {name}")
			print(f"  {exc}")
			continue

		normalized_left_json = normalize_json_for_compare(left_json)
		normalized_right_json = normalize_json_for_compare(right_json)
		diff_lines = one_line_diff_summary(normalized_left_json, normalized_right_json)

		if diff_lines == ["no visible field-level diff"]:
			same += 1
		else:
			different += 1
			print(f"[DIFF] {name}")
			for diff_line in diff_lines:
				print(f"  {diff_line}")

	return same, different, invalid_json


def print_missing(
	side_name: str,
	names: List[str],
	files_by_name: Dict[str, List[FileRecord]],
	root: Path,
) -> None:
	if not names:
		return

	print(f"\nFiles present only in {side_name} ({len(names)}):")
	for name in names:
		for record in files_by_name[name]:
			print(f"  - {record.path.relative_to(root)}")


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Compare JSON files with the same filename across two folders."
	)
	parser.add_argument("folder_a", help="First folder")
	parser.add_argument("folder_b", help="Second folder")
	args = parser.parse_args()

	folder_a = Path(args.folder_a).resolve()
	folder_b = Path(args.folder_b).resolve()

	if not folder_a.is_dir():
		print(f"Error: '{folder_a}' is not a directory")
		return 2
	if not folder_b.is_dir():
		print(f"Error: '{folder_b}' is not a directory")
		return 2

	files_a = collect_files(folder_a)
	files_b = collect_files(folder_b)

	only_a = sorted(set(files_a.keys()) - set(files_b.keys()))
	only_b = sorted(set(files_b.keys()) - set(files_a.keys()))

	same, different, invalid_json = compare_pairs(folder_a, folder_b, files_a, files_b)

	print_missing("folder A", only_a, files_a, folder_a)
	print_missing("folder B", only_b, files_b, folder_b)

	print("\nSummary:")
	print(f"  Same files       : {same}")
	print(f"  Different files  : {different}")
	print(f"  Invalid JSON     : {invalid_json}")
	print(f"  Only in folder A : {len(only_a)}")
	print(f"  Only in folder B : {len(only_b)}")

	if different or invalid_json or only_a or only_b:
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
