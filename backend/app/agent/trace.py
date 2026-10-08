"""Readable summaries of agent steps, shared by the CLI's --trace and the API's `step` events."""


def describe_step(node: str, changes: dict) -> dict:
    """Summarise what one graph node just did: a short `label`, plus structured details."""
    if node == "router":
        route, query = changes["route"], changes["query"]
        label = f"Route: {route}" + (f" · search query '{query}'" if route == "retrieve" else "")
        return {"node": node, "label": label, "route": route, "query": query}

    if node == "retrieve":
        query, count = changes["queries"][-1], len(changes["candidates"])
        return {"node": node, "label": f"Searched for '{query}': {count} results", "query": query, "results": count}

    if node == "grade":
        kept = [{"n": s["n"], "citation": s["citation"]} for s in changes.get("sources", [])]
        label = f"Kept {len(kept)} relevant: " + "; ".join(f"[{s['n']}] {s['citation']}" for s in kept)
        return {"node": node, "label": label if kept else "No relevant passages", "relevant": kept}

    if node == "rewrite":
        return {"node": node, "label": f"Rephrased the search: '{changes['query']}'", "query": changes["query"]}

    if node in ("generate", "respond"):
        if changes.get("answer"):
            cited = [s["n"] for s in changes.get("citations", [])]
            return {"node": node, "label": "Wrote the answer" + (f" (cites {cited})" if cited else ""), "cited": cited}
        calls = [{"name": c["name"], "args": c["args"]} for c in changes["scratch"][-1].tool_calls]
        label = "Calling " + ", ".join(f"{c['name']}({', '.join(map(repr, c['args'].values()))})" for c in calls)
        return {"node": node, "label": label, "tool_calls": calls}

    if node == "tools":
        # The tools node appends one ToolMessage per call at the end of scratch.
        results = []
        for message in reversed(changes["scratch"]):
            if message.type != "tool":
                break
            results.insert(0, {"name": message.name, "result": message.content.splitlines()[0][:200]})
        return {"node": node, "label": " | ".join(f"{r['name']} → {r['result']}" for r in results), "results": results}

    return {"node": node, "label": node}
