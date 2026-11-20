"""Disposition force-dirigée (Fruchterman-Reingold) déterministe.

Positions normalisées dans [0, 1]². O(n²) : convient à quelques centaines de
nœuds, ce qui couvre largement l'usage local.
"""

from __future__ import annotations

import numpy as np

from face_analyse.graph.model import Graph


def force_directed(graph: Graph, iterations: int = 220, seed: int = 7) -> dict[str, tuple[float, float]]:
    nodes = graph.nodes
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0].id: (0.5, 0.5)}

    index = {node.id: i for i, node in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    pos = rng.random((n, 2)) * 0.8 + 0.1

    edges = np.array([[index[e.src], index[e.dst]] for e in graph.edges
                      if e.src in index and e.dst in index], dtype=np.int64)

    k = 1.0 / np.sqrt(n)          # distance idéale
    temp = 0.12
    cool = temp / (iterations + 1)

    for _ in range(iterations):
        disp = np.zeros((n, 2))
        # Répulsion entre toutes les paires (vectorisé).
        delta = pos[:, None, :] - pos[None, :, :]        # (n, n, 2)
        dist = np.linalg.norm(delta, axis=2) + 1e-9
        rep = (k * k) / dist                              # (n, n)
        np.fill_diagonal(rep, 0.0)
        disp += np.einsum("ijk,ij->ik", delta / dist[:, :, None], rep)

        # Attraction le long des liens.
        if len(edges):
            d = pos[edges[:, 0]] - pos[edges[:, 1]]
            dl = np.linalg.norm(d, axis=1) + 1e-9
            force = (dl * dl) / k
            vec = (d / dl[:, None]) * force[:, None]
            np.add.at(disp, edges[:, 0], -vec)
            np.add.at(disp, edges[:, 1], vec)

        length = np.linalg.norm(disp, axis=1) + 1e-9
        pos += (disp / length[:, None]) * np.minimum(length, temp)[:, None]
        pos = np.clip(pos, 0.02, 0.98)
        temp -= cool

    # Normalisation finale dans [0, 1].
    lo, hi = pos.min(0), pos.max(0)
    span = np.where(hi - lo < 1e-6, 1.0, hi - lo)
    pos = (pos - lo) / span
    return {nodes[i].id: (float(pos[i, 0]), float(pos[i, 1])) for i in range(n)}
