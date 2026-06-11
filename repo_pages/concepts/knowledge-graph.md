---
description: "How Hebb Mind builds a tag-based knowledge graph (NetworkX) that links AI agent memories, powering graph tag-match in hybrid search alongside vector and keyword retrieval."
---

# Knowledge Graph

Hebb Mind maintains a tag-based knowledge graph that captures relationships between concepts across all memories. The graph is backed by **NetworkX** and persisted as a JSON file.

## Structure

- **Nodes** -- tags extracted during memory consolidation (e.g., "python", "dark-mode", "deployment")
- **Edges** -- co-occurrence relationships between tags that appear in the same memory, weighted by frequency

When a memory with tags `["python", "testing", "pytest"]` is consolidated, edges are created (or strengthened) between all tag pairs: python-testing, python-pytest, and testing-pytest.

## Storage

The knowledge graph is stored as `knowledge_graph.json` in the workspace directory. The file path is automatically derived from the workspace and cannot be configured independently. To change where the knowledge graph file is stored, set the workspace directory:

```bash
# Check the current workspace directory
hebb config get workspace

# Override the workspace directory
hebb config set home /data/hebb

# Or use the HEBB_HOME environment variable
export HEBB_HOME=/data/hebb
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

### 1. Tag-match channel

During search, three retrieval paths run concurrently and are fused with reciprocal-rank fusion:

- Vector similarity search
- Keyword (full-text) search
- **Graph tag-match** -- the query is tokenized and each token is matched against existing tag ids/labels (exact or short-substring match); memories carrying a matched tag, plus their 1-hop tag neighbors, are collected.

The graph channel is a lexical tag matcher, not a semantic traversal: it cannot find a memory whose tags share no token with the query. Vector and keyword search (plus the cross-encoder rerank) carry the bulk of recall quality; the graph channel mainly adds tag-linked siblings.

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
