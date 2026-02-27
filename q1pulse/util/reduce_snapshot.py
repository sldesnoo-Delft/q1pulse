from typing import Any


def reduce_snapshot(snapshot: dict[str, Any], name: str | None = None):
    """Removes meaningless entries from snapshot"""

    if "__class__" not in snapshot:
        result = {}
        for key, value in snapshot.items():
            if isinstance(value, dict):
                value = reduce_snapshot(value, name=key)
                if not value:
                    continue
            result[key] = value
        return result
    else:
        exclude_keys = [
            "__class__",
            "full_name",
            "functions",
            "instrument",
            "instrument_name",
            "raw_value",
            "val_mapping",
            "validators",
            "vals",
            ]
        exclude_if_empty = [
            "inter_delay",
            "post_delay",
            "unit",
            ]
        exclude_if_name = [
            "name",
            "label",
            ]

        result = {}
        for key, value in snapshot.items():
            if key in exclude_keys:
                continue
            if key in exclude_if_empty and not value:
                continue
            if key in exclude_if_name and value == name:
                continue
            if isinstance(value, dict):
                value = reduce_snapshot(value, name=key)
                if not value:
                    continue
            result[key] = value
        return result
