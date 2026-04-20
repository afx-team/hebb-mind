"""Knowledge graph backed by NetworkX with JSON file persistence."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from hippocampus.models.graph import (
    GraphQueryResult,
    KnowledgeGraphState,
    TagEdge,
    TagNode,
)


class KnowledgeGraph:
    """Tag-based knowledge graph with file-backed persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.graph: nx.Graph = nx.Graph()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            state = KnowledgeGraphState.model_validate_json(self.path.read_text())
            for node in state.nodes:
                self.graph.add_node(node.id, **node.model_dump())
            for edge in state.edges:
                self.graph.add_edge(
                    edge.source,
                    edge.target,
                    relation=edge.relation,
                    weight=edge.weight,
                    source=edge.source,
                    target=edge.target,
                )
        except Exception:
            # Corrupt file — start fresh
            self.graph = nx.Graph()

    def save(self) -> None:
        """Persist graph to JSON file."""
        nodes = []
        for node_id in self.graph.nodes:
            data = self.graph.nodes[node_id]
            nodes.append(
                TagNode(
                    id=data.get("id", node_id),
                    label=data.get("label", node_id),
                    description=data.get("description", ""),
                    memory_ids=data.get("memory_ids", []),
                    weight=data.get("weight", 1.0),
                )
            )

        edges = []
        for u, v in self.graph.edges:
            data = self.graph.edges[u, v]
            edges.append(
                TagEdge(
                    source=u,
                    target=v,
                    relation=data.get("relation", "related"),
                    weight=data.get("weight", 1.0),
                )
            )

        state = KnowledgeGraphState(nodes=nodes, edges=edges)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(state.model_dump_json(indent=2))

    def add_tag(self, tag_id: str, memory_id: str, label: str = "") -> None:
        """Add or update a tag node, linking it to a memory."""
        tag_id = tag_id.lower().strip()
        if self.graph.has_node(tag_id):
            data = self.graph.nodes[tag_id]
            if memory_id not in data.get("memory_ids", []):
                data.setdefault("memory_ids", []).append(memory_id)
            data["weight"] = len(data["memory_ids"])
        else:
            self.graph.add_node(
                tag_id,
                id=tag_id,
                label=label or tag_id,
                description="",
                memory_ids=[memory_id],
                weight=1.0,
            )

    def remove_memory_from_tags(self, memory_id: str) -> None:
        """Remove a memory reference from all tags."""
        for node_id in list(self.graph.nodes):
            data = self.graph.nodes[node_id]
            mids = data.get("memory_ids", [])
            if memory_id in mids:
                mids.remove(memory_id)
                data["weight"] = len(mids)

    def add_edge(self, source: str, target: str, relation: str = "related") -> None:
        """Add or update an edge between two tags."""
        source = source.lower().strip()
        target = target.lower().strip()
        if source == target:
            return
        if self.graph.has_edge(source, target):
            self.graph.edges[source, target]["weight"] += 1.0
        else:
            self.graph.add_edge(
                source,
                target,
                relation=relation,
                weight=1.0,
                source=source,
                target=target,
            )

    def update_from_tags(self, tags: list[str], memory_id: str) -> None:
        """Add tags from a memory, creating co-occurrence edges between them."""
        normalized = [t.lower().strip() for t in tags if t.strip()]
        for tag in normalized:
            self.add_tag(tag, memory_id)

        # Create co-occurrence edges
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                self.add_edge(normalized[i], normalized[j])

    def get_tag(self, tag_id: str) -> TagNode | None:
        """Get a single tag node."""
        tag_id = tag_id.lower().strip()
        if not self.graph.has_node(tag_id):
            return None
        data = self.graph.nodes[tag_id]
        return TagNode(
            id=data.get("id", tag_id),
            label=data.get("label", tag_id),
            description=data.get("description", ""),
            memory_ids=data.get("memory_ids", []),
            weight=data.get("weight", 1.0),
        )

    def query_neighbors(self, tag_id: str, depth: int = 1) -> GraphQueryResult:
        """Get neighbors of a tag up to a given depth."""
        tag_id = tag_id.lower().strip()
        if not self.graph.has_node(tag_id):
            return GraphQueryResult()

        # BFS to collect nodes within depth
        visited = set()
        queue = [(tag_id, 0)]
        while queue:
            current, d = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if d < depth:
                for neighbor in self.graph.neighbors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, d + 1))

        nodes = []
        for nid in visited:
            node = self.get_tag(nid)
            if node:
                nodes.append(node)

        edges = []
        for u, v in self.graph.edges:
            if u in visited and v in visited:
                data = self.graph.edges[u, v]
                edges.append(
                    TagEdge(
                        source=u,
                        target=v,
                        relation=data.get("relation", "related"),
                        weight=data.get("weight", 1.0),
                    )
                )

        return GraphQueryResult(nodes=nodes, edges=edges)

    def search_path(self, from_tag: str, to_tag: str) -> GraphQueryResult:
        """Find shortest path between two tags."""
        from_tag = from_tag.lower().strip()
        to_tag = to_tag.lower().strip()
        if not self.graph.has_node(from_tag) or not self.graph.has_node(to_tag):
            return GraphQueryResult()

        try:
            path = nx.shortest_path(self.graph, from_tag, to_tag)
        except nx.NetworkXNoPath:
            return GraphQueryResult(paths=[])

        nodes = [self.get_tag(nid) for nid in path if self.get_tag(nid)]
        edges = []
        for i in range(len(path) - 1):
            if self.graph.has_edge(path[i], path[i + 1]):
                data = self.graph.edges[path[i], path[i + 1]]
                edges.append(
                    TagEdge(
                        source=path[i],
                        target=path[i + 1],
                        relation=data.get("relation", "related"),
                        weight=data.get("weight", 1.0),
                    )
                )

        return GraphQueryResult(nodes=nodes, edges=edges, paths=[path])

    def search_tags(self, query: str) -> list[TagNode]:
        """Substring search on tag IDs and labels."""
        query = query.lower().strip()
        results = []
        for node_id in self.graph.nodes:
            data = self.graph.nodes[node_id]
            label = data.get("label", "")
            if query in node_id or query in label.lower():
                results.append(
                    TagNode(
                        id=data.get("id", node_id),
                        label=data.get("label", node_id),
                        description=data.get("description", ""),
                        memory_ids=data.get("memory_ids", []),
                        weight=data.get("weight", 1.0),
                    )
                )
        return results

    def get_all_tags(self) -> list[TagNode]:
        """Return all tag nodes."""
        return [self.get_tag(nid) for nid in self.graph.nodes if self.get_tag(nid)]  # type: ignore[misc]

    def export(self) -> KnowledgeGraphState:
        """Export the full graph state."""
        nodes = self.get_all_tags()
        edges = []
        for u, v in self.graph.edges:
            data = self.graph.edges[u, v]
            edges.append(
                TagEdge(
                    source=u,
                    target=v,
                    relation=data.get("relation", "related"),
                    weight=data.get("weight", 1.0),
                )
            )
        return KnowledgeGraphState(nodes=nodes, edges=edges)
