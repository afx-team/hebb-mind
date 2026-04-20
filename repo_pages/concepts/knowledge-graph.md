# Knowledge Graph

Hippocampus maintains a tag-based knowledge graph that captures relationships between concepts across all memories. The graph is backed by **NetworkX** and persisted as a JSON file.

## Structure

- **Nodes** -- tags extracted during memory consolidation (e.g., "python", "dark-mode", "deployment")
- **Edges** -- co-occurrence relationships between tags that appear in the same memory, weighted by frequency

When a memory with tags `["python", "testing", "pytest"]` is consolidated, edges are created (or strengthened) between all tag pairs: python-testing, python-pytest, and testing-pytest.

## Storage

The knowledge graph is stored in a JSON file (default: `knowledge_graph.json`). The path is configurable:

```bash
hippocampus config set kg_path knowledge_graph.json
```

## API

### List All Tags

```bash
curl http://localhost:8321/api/v1/graph/tags
```

### Get a Single Tag

```bash
curl http://localhost:8321/api/v1/graph/tags/python
```

### Query Neighbors

Find tags connected to a given tag, up to a specified depth:

```bash
curl http://localhost:8321/api/v1/graph/neighbors/python?depth=2
```

This returns all tags within 2 hops of "python" in the graph.

### Find Shortest Path

Find the shortest path between two tags:

```bash
curl "http://localhost:8321/api/v1/graph/path?from=python&to=machine-learning"
```

### Export Full Graph

Export the complete graph structure for external analysis or visualization:

```bash
curl http://localhost:8321/api/v1/graph/export
```

## Role in Search

The knowledge graph plays two roles during memory retrieval:

### 1. Parallel Recall

During search, three retrieval paths run in parallel:

- Vector similarity search
- Keyword (full-text) search
- **Graph-based retrieval** -- the query's tags are used to traverse the knowledge graph and find related memories

### 2. Post-Expansion

After the initial search results are scored, the top results are expanded by following knowledge graph edges. This surfaces related memories that may not have matched the query directly but are connected through shared concepts.

For example, a search for "deployment" might expand to include memories tagged with "docker" or "CI/CD" if those tags are strongly connected in the graph.

## Web Console Visualization

The Web Console includes a **force-directed graph visualization** that lets you explore the knowledge graph interactively. You can:

- View all tags and their connections
- Click on a tag to see its neighbors
- Filter by tag name or connection strength
- Explore paths between concepts

Access it at [http://localhost:8321/](http://localhost:8321/) under the Graph tab.
