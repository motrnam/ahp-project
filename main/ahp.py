from __future__ import annotations

from typing import ClassVar

import numpy as np


class AHPNode:
    """A node in the AHP hierarchy.

    Parameters
    ----------
    name : str
        Name of this criterion (or the goal at the root).
    comparisons : dict[(str, str), float] | None
        Pairwise comparisons among the *children* of this node.
        Keys are ordered pairs ``(a, b)`` meaning "a is preferred over b
        by the given factor".  Only the upper triangle is required.
    alternatives : dict[(str, str), float] | None
        Pairwise comparisons among the *decision alternatives* under this
        criterion.  Meaningful only on leaf criteria (no children).
    """

    RI_TABLE: ClassVar = {
        1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24,
        7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49, 11: 1.51, 12: 1.48,
        13: 1.56, 14: 1.57, 15: 1.59,
    }

    def __init__(
        self,
        name: str,
        comparisons: dict[tuple[str, str], float] | None = None,
        alternatives: dict[tuple[str, str], float] | None = None,
    ):
        self.name = name
        self.comparisons = comparisons or {}
        self.alternatives = alternatives
        self.children: list["AHPNode"] = []

        self.local_weights: dict[str, float] = {}
        self.alternative_weights: dict[str, float] = {}

        self.consistency_ratio: float = 0.0
        self.lambda_max: float = 0.0
        self.alt_consistency_ratio: float = 0.0           
        self.alt_lambda_max: float = 0.0                  

        self._build_matrix()
        if self.alternatives:                             
            self._compute_alternative_weights()

    # ------------------------------------------------------------------ #
    #  Matrix / eigenvector helpers (shared by both layers)              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_pairwise_matrix(
        comparisons: dict[tuple[str, str], float],
    ) -> tuple[list[str], np.ndarray]:
        criteria: list[str] = []
        for a, b in comparisons:
            if a not in criteria:
                criteria.append(a)
            if b not in criteria:
                criteria.append(b)

        n = len(criteria)
        matrix = np.ones((n, n), dtype=float)
        idx = {name: i for i, name in enumerate(criteria)}
        for (a, b), val in comparisons.items():
            i, j = idx[a], idx[b]
            matrix[i, j] = val
            matrix[j, i] = 1.0 / val if val != 0 else 0.0
        return criteria, matrix

    @staticmethod
    def _eigen_weights(
        matrix: np.ndarray, labels: list[str]
    ) -> tuple[dict[str, float], float, float]:
        """Return (weights, lambda_max, consistency_ratio)."""
        n = len(labels)
        if n == 0:
            return {}, 0.0, 0.0
        if n == 1:
            return {labels[0]: 1.0}, 1.0, 0.0

        eigenvalues, eigenvectors = np.linalg.eig(matrix)
        max_idx = int(np.argmax(eigenvalues.real))
        lambda_max = float(eigenvalues.real[max_idx])
        principal = np.abs(eigenvectors[:, max_idx].real)
        weights = principal / principal.sum()
        lw = {name: float(weights[i]) for i, name in enumerate(labels)}

        if n <= 2:
            cr = 0.0
        else:
            ci = (lambda_max - n) / (n - 1)
            ri = AHPNode.RI_TABLE.get(n, 1.59)
            cr = ci / ri if ri > 0 else 0.0
        return lw, lambda_max, cr

    # ------------------------------------------------------------------ #
    #  Criteria layer                                                    #
    # ------------------------------------------------------------------ #

    def _build_matrix(self):
        self.criteria, self.matrix = self._build_pairwise_matrix(self.comparisons)
        self._compute_weights()

    def _compute_weights(self):
        self.local_weights, self.lambda_max, self.consistency_ratio = \
            self._eigen_weights(self.matrix, self.criteria)

    # ------------------------------------------------------------------ #
    #  Alternatives layer (NEW)                                          #
    # ------------------------------------------------------------------ #

    def _compute_alternative_weights(self):
        labels, matrix = self._build_pairwise_matrix(self.alternatives)
        self.alternative_names = labels
        self.alternative_weights, self.alt_lambda_max, self.alt_consistency_ratio = \
            self._eigen_weights(matrix, labels)

    def add_child(self, child: "AHPNode"):
        self.children.append(child)

    # ------------------------------------------------------------------ #
    #  Global weights of criteria (leaves)                               #
    # ------------------------------------------------------------------ #

    def compute_global_weights(
        self,
        parent_weight: float = 1.0,
        out: dict[str, float] | None = None,
        prefix: str = "",
    ) -> dict[str, float]:
        if out is None:
            out = {}

        if not self.children:
            name = self.criteria[0] if len(self.criteria) == 1 else self.name
            out[prefix + name] = parent_weight
            return out

        for child in self.children:
            cw = self.local_weights.get(child.name, 0.0)
            child.compute_global_weights(parent_weight * cw, out, prefix)
        return out

    # ------------------------------------------------------------------ #
    #  NEW: global weights of alternatives                               #
    # ------------------------------------------------------------------ #

    def compute_alternative_scores(
        self, parent_weight: float = 1.0
    ) -> dict[str, float]:
        """Return the final score of every alternative (already normalized)."""
        scores: dict[str, float] = {}
        self._accumulate_alternative_scores(parent_weight, scores)
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}
        return scores

    def _accumulate_alternative_scores(
        self, parent_weight: float, scores: dict[str, float]
    ) -> None:
        if not self.children:
            # leaf criterion: distribute its global weight over alternatives
            for alt, w in self.alternative_weights.items():
                scores[alt] = scores.get(alt, 0.0) + parent_weight * w
            return
        for child in self.children:
            cw = self.local_weights.get(child.name, 0.0)
            child._accumulate_alternative_scores(parent_weight * cw, scores)

    def rank_alternatives(self) -> dict[str, float]:
        return dict(sorted(
            self.compute_alternative_scores().items(), key=lambda kv: -kv[1]
        ))

    # ------------------------------------------------------------------ #
    #  Reporting                                                         #
    # ------------------------------------------------------------------ #

    def report(
        self,
        show: bool = True,
        complete: bool = True,
        verbose: bool = True,
        indent: int = 0,
    ):
        pad = "\t" * indent
        if show:
            print(f"{pad}Node: {self.name}")
            print(f"{pad}  Criteria: {self.criteria}")
            print(f"{pad}  Local weights: {self.local_weights}")
            print(f"{pad}  Lambda max: {self.lambda_max:.4f}")
            print(f"{pad}  Consistency ratio: {self.consistency_ratio:.4f}")
            if self.consistency_ratio > 0.1:
                print(f"{pad}  ⚠️  Consistency ratio > 0.1 — comparisons "
                      "may be inconsistent!")
            if self.alternative_weights:                       
                print(f"{pad}  Alternatives: {self.alternative_weights}")
                print(f"{pad}  Alt lambda max: {self.alt_lambda_max:.4f}")
                print(f"{pad}  Alt consistency ratio: "
                      f"{self.alt_consistency_ratio:.4f}")
                if self.alt_consistency_ratio > 0.1:
                    print(f"{pad}  ⚠️  Alternative CR > 0.1!")
        for c in self.children:
            c.report(show=show, complete=complete, verbose=verbose,
                     indent=indent + 1)

    def _is_with(self, criteria_name: str) -> bool:
        return any(child.name == criteria_name for child in self.children)

    def tree_show(
        self,
        indent: int = 0,
        _parent_weight: float = 1.0,
    ):
        pad = "  " * indent
        branch = "└── " if indent else ""
        print(f"{pad}{branch}{self.name}")

        for cri in self.criteria:
            if self._is_with(cri):
                continue
            local_w = self.local_weights.get(cri, 0.0)
            global_w = local_w * _parent_weight
            print(f"{pad}  ├── {cri}  "
                  f"[local: {local_w:.4f}, global: {global_w:.4f}]")

            # --- NEW: show alternative priorities under this leaf ---
            # The leaf node object that matches `cri` lives among children.
            leaf = next((c for c in self.children if c.name == cri), None)
            if leaf and leaf.alternative_weights:
                for alt, aw in sorted(leaf.alternative_weights.items(),
                                      key=lambda kv: -kv[1]):
                    print(f"{pad}  │     • {alt}: "
                          f"local {aw:.4f} → global {aw * global_w:.4f}")

        for child in self.children:
            child.tree_show(indent + 1,
                            _parent_weight=_parent_weight *
                            self.local_weights.get(child.name, 0.0))

    @property
    def target_weights(self) -> dict[str, float]:
        return self.compute_global_weights()
    


    def to_dict(self) -> dict:
        """Serialize this node (and its subtree) to a plain dict."""
        return {
            "name": self.name,
            "comparisons": {
                f"{a}|{b}": v for (a, b), v in self.comparisons.items()
            },
            "alternatives": (
                {f"{a}|{b}": v for (a, b), v in self.alternatives.items()}
                if self.alternatives else None
            ),
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AHPNode":
        """Rebuild a node (and its subtree) from a dict."""
        def _parse(pairs):
            if not pairs:
                return None
            out = {}
            for k, v in pairs.items():
                a, b = k.split("|", 1)
                out[(a, b)] = float(v)
            return out

        node = cls(
            name=data["name"],
            comparisons=_parse(data.get("comparisons")),
            alternatives=_parse(data.get("alternatives")),
        )
        for child_data in data.get("children", []):
            node.add_child(cls.from_dict(child_data))
        return node
