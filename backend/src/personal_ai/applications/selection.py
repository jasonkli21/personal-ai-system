"""Closed deployment selection; discovery never executes unselected plugins."""

import json
import os
import re


def validate_selection(names):
    if (
        not isinstance(names, (tuple, list))
        or len(names) > 32
        or any(
            not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name)
            for name in names
        )
        or len(names) != len(set(names))
    ):
        raise ValueError("contribution_selection_invalid")
    return tuple(sorted(names))


def selected_contribution_names():
    try:
        names = json.loads(os.environ.get("APPLICATION_CONTRIBUTIONS", "[]"))
    except ValueError:
        raise ValueError("contribution_selection_invalid") from None
    return validate_selection(names)


def load_selected_entry_points(points, names):
    """Validate the entire selected inventory before any trusted code executes."""
    selected = validate_selection(names)
    inventory = {}
    for point in points:
        if point.name in selected:
            if point.name in inventory:
                raise ValueError("contribution_entry_point_duplicate")
            inventory[point.name] = point
    if set(selected) - inventory.keys():
        raise ValueError("contribution_not_installed")
    return tuple((name, inventory[name].load()) for name in selected)
