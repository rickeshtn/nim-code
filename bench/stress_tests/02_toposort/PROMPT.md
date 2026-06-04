Paste into nimcode:

---

Implement topological sort in `toposort.py`. Function signature:

    def toposort(graph: dict[str, list[str]]) -> list[str] | None

`graph` maps each node to the list of nodes it depends on (its prerequisites). Return a valid linear ordering where every node appears after its prerequisites. If the graph has a cycle, return `None`. Nodes appearing only as prerequisites (not as keys) are treated as having no prerequisites.

Then run `./score.sh`. If it prints `FAIL`, fix and re-run. Only stop when it prints `PASS`. Do not modify the test file.
