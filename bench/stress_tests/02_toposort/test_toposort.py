from toposort import toposort


def _is_valid_order(order, graph):
    pos = {n: i for i, n in enumerate(order)}
    for node, deps in graph.items():
        for d in deps:
            if d not in pos or pos[d] >= pos[node]:
                return False
    return True


def test_linear_chain():
    g = {"c": ["b"], "b": ["a"], "a": []}
    out = toposort(g)
    assert out is not None
    assert _is_valid_order(out, g)
    assert set(out) >= {"a", "b", "c"}


def test_diamond():
    g = {"d": ["b", "c"], "b": ["a"], "c": ["a"], "a": []}
    out = toposort(g)
    assert out is not None
    assert _is_valid_order(out, g)


def test_cycle_detected():
    g = {"a": ["b"], "b": ["c"], "c": ["a"]}
    assert toposort(g) is None


def test_self_loop_is_cycle():
    g = {"a": ["a"]}
    assert toposort(g) is None


def test_implicit_leaf_nodes():
    # 'a' is only referenced as a dependency, never as a key
    g = {"b": ["a"], "c": ["a", "b"]}
    out = toposort(g)
    assert out is not None
    assert _is_valid_order(out, g)
    assert "a" in out


def test_empty():
    assert toposort({}) == [] or toposort({}) == []
