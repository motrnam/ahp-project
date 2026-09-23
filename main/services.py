from fractions import Fraction
from math import prod

from .ahp import AHPNode

THRESHOLD = 0.1


def parse_ahp_value(val_str):
    if isinstance(val_str, (int, float)):
        return val_str 
    if not val_str or val_str.strip() in ("", "—"):
        return None
    try:
        return float(Fraction(val_str))
    except (ValueError, ZeroDivisionError):
        return None


def geometric_mean(values):
    """Geometric mean of a list of positive floats."""
    values = [v for v in values if v is not None and v > 0]
    if not values:
        return None
    return prod(values) ** (1 / len(values))

def extract_ahpy_model(post_data, questionnaire):
    alternatives = questionnaire.questions.get("alternatives", [])

    inconsistent_nodes = []

    def walk(node, parent_name):
        comparing = {}
        for n1 in node:
            for n2 in node:
                if n1.get("index", -1) < n2.get("index", -2):
                    field_name = (
                        f"criteria___{n1.get('index', -1)}___{n2.get('index', -2)}"
                    )
                    val_raw = post_data.get(field_name)
                    val = parse_ahp_value(val_raw)
                    if val is not None:
                        comparing[(n1.get("name", ""), n2.get("name", ""))] = val

        node_model = AHPNode(parent_name, comparing)

        for n in node:
            children = n.get("children", [])
            alt_dict = {}
            if len(children) == 0:
                for i in range(len(alternatives)):
                    for j in range(i + 1, len(alternatives)):
                        alternatives_field_name = (
                            f"alternatives___{i}___{j}___{n.get('index', -7)}"
                        )
                        val_raw = post_data.get(alternatives_field_name)
                        val = parse_ahp_value(val_raw)
                        alt_dict[(alternatives[i], alternatives[j])] = val
                        node_model.alternatives = alt_dict
                        node_model._compute_alternative_weights()
            if len(children) >= 2:
                child_model = walk(children, n.get("name"))
                node_model.add_child(child_model)
        if node_model.consistency_ratio > THRESHOLD:
            inconsistent_nodes.append(node_model)
        return node_model

    root_model = walk(questionnaire.questions.get("questions", []), "main")

    root_model.tree_show()

    return {
        "root": root_model,
        "global_weights": root_model.target_weights,
        "inconsistent_nodes": inconsistent_nodes,
    }


def build_comparison_groups(tree):
    """
    Walk the tree and produce one comparison group per parent
    that has 2+ children.

    Returns a list of dicts:
    {
        "parent_name": str | None,   # None => root / top goal
        "path": str,                 # e.g. "klfkldkf > dkfldfk"
        "level": int,                # 1, 2, 3, ...
        "items": [ {name, index}, ... ],
    }
    """
    groups = []

    def walk(node, parent_name, path, level):
        children = node.get("children") or []
        if len(children) >= 2:
            groups.append(
                {
                    "parent_name": parent_name,
                    "path": path,
                    "level": level,
                    "items": [
                        {
                            "name": c.get("name", ""),
                            "index": i,
                            "index2": c.get("index", 0),
                        }
                        for i, c in enumerate(children)
                    ],
                }
            )

        for child in children:
            child_path = f"{path} > {child['name']}" if path else child["name"]
            walk(child, child["name"], child_path, level + 1)

    # Treat the top level of the list as children of the (virtual) root goal
    if len(tree) >= 2:
        groups.append(
            {
                "parent_name": None,  # top goal
                "path": "هدف اصلی",
                "level": 1,
                "items": [
                    {
                        "name": c.get("name", ""),
                        "index": i,
                        "index2": c.get("index", -1),
                    }
                    for i, c in enumerate(tree)
                ],
            }
        )

    for top in tree:
        walk(top, top["name"], top["name"], 2)
    return groups


def build_alternatives_groups(leaf_criteria_or_groups, alternatives: list):
    result = []
    if len(alternatives) < 2:
        return result

    alt_items = []
    for i, alt in enumerate(alternatives):
        if isinstance(alt, dict):
            alt_items.append(
                {"name": alt.get("name", ""), "index": alt.get("index", i)}
            )
        else:
            alt_items.append({"name": str(alt), "index": i})

    for crit_idx, group in enumerate(leaf_criteria_or_groups):
        criterion_title = (
            group.get("parent_name") or group.get("path") or f"معیار {crit_idx + 1}"
        )
        result.append(
            {
                "criterion_name": criterion_title,
                "criterion_index": crit_idx,
                "items": alt_items,
            }
        )

    return result


def build_alternatives_groups2(tree, alternatives: list):
    result = []

    comb_of_2 = [
        ({"name": alternatives[i], "index": i}, {"name": alternatives[j], "index": j})
        for i in range(len(alternatives))
        for j in range(i + 1, len(alternatives))
    ]

    def walk(node, parent_name, path, level):
        children = node.get("children") or []
        name = node.get("name") or "fuck"
        result.append({"name": name, "level": level, "alternatives": comb_of_2})

        for child in children:
            child_path = f"{path} > {child['name']}" if path else child["name"]
            walk(child, child["name"], child_path, level + 1)

    # handle both a single root dict and a list of root dicts
    if isinstance(tree, list):
        for root in tree:
            walk(root, None, "", 0)
    else:
        walk(tree, None, "", 0)

    result.sort(key=lambda x: x["level"])

    return result
