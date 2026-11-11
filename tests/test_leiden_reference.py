"""Compare the C++ Leiden result with leidenalg on seeded weighted planted graphs."""
import os
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import igraph
import leidenalg

TOOL = os.environ.get("GRAPH_TOOL")

@unittest.skipUnless(TOOL and Path(TOOL).is_file(), "set GRAPH_TOOL to the built C++ executable")
class LeidenReferenceCases(unittest.TestCase):
    def test_planted_graphs_across_resolutions(self):
        # leidenalg's RB objective divided by 2m equals this project's generalized modularity.
        # Across 100 fixed random and planted cases require absolute difference <= .03.
        max_difference = 0.0
        for model in ('planted','random'):
          for gamma in (.3, .5, .8, 1.0, 1.2):
            for seed in range(10):
                rng = random.Random((900 if model=='planted' else 1900) + seed)
                n = 12 if model=='planted' else 14
                planted = [i // 4 for i in range(n)]
                edges = []
                for i in range(n):
                    for j in range(i + 1, n):
                        probability = (.72 if planted[i] == planted[j] else .08) if model=='planted' else .28
                        if rng.random() < probability:
                            edges.append((i, j, round(.25 + rng.random(), 4)))
                if model=='planted':
                    for group in range(3):
                        for i in range(group * 4, (group + 1) * 4 - 1):
                            if not any(a == i and b == i + 1 for a, b, _ in edges):
                                edges.append((i, i + 1, 1.0))
                if not edges:edges=[(0,1,1.0)]
                with tempfile.TemporaryDirectory() as td:
                    edge_file = Path(td) / "graph.edges"
                    community_file = Path(td) / "communities.tsv"
                    edge_file.write_text("".join(f"{a}\t{b}\t{w}\n" for a, b, w in edges))
                    proc = subprocess.run(
                        [TOOL, "--mode", "leiden", "--input", str(edge_file), "--output", str(community_file),
                         "--nodes", str(n), "--resolution", str(gamma), "--seed", str(seed)],
                        check=True, text=True, capture_output=True)
                    own_q = float(re.search(r"modularity=([-+0-9.eE]+)", proc.stdout).group(1))
                    membership = [int(line.split()[1]) for line in community_file.read_text().splitlines()]
                    adjacency = [set() for _ in range(n)]
                    for a, b, _ in edges:
                        adjacency[a].add(b); adjacency[b].add(a)
                    for cid in set(membership):
                        members = {i for i, value in enumerate(membership) if value == cid}
                        seen = {next(iter(members))}; stack = list(seen)
                        while stack:
                            u = stack.pop()
                            for v in adjacency[u] & members - seen:
                                seen.add(v); stack.append(v)
                        self.assertEqual(seen, members, f"disconnected community at {model}, gamma={gamma}, seed={seed}")
                    graph = igraph.Graph(n=n, edges=[(a, b) for a, b, _ in edges], directed=False)
                    weights = [w for _, _, w in edges]
                    ref = leidenalg.find_partition(
                        graph, leidenalg.RBConfigurationVertexPartition, weights=weights,
                        resolution_parameter=gamma, seed=seed, n_iterations=-1)
                    total_weight = sum(weights)
                    ref_q = ref.quality() / (2 * total_weight)
                    difference = abs(own_q - ref_q)
                    max_difference = max(max_difference, difference)
                    self.assertLessEqual(difference, .03, f"Q difference {difference} at {model}, gamma={gamma}, seed={seed}")
        self.assertLessEqual(max_difference, .03)

if __name__ == "__main__":
    unittest.main()
