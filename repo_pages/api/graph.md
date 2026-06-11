---
description: "REST API for the tag relationship graph built during AI agent memory consolidation: list and inspect tags, query neighbors by depth, find shortest paths, and export nodes and edges."
---

# Knowledge Graph API

The knowledge graph API provides access to the tag-based relationship graph built during memory consolidation.

## List Tags

Retrieve all tags in the knowledge graph, optionally filtered by search query.

```
GET /api/v1/graph/tags
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search filter for tag names |

**Example:**

```bash
# List all tags
curl http://localhost:8321/api/v1/graph/tags

# Search for tags containing "python"
curl "http://localhost:8321/api/v1/graph/tags?q=python"
```

## Get Tag

Retrieve details for a single tag.

```
GET /api/v1/graph/tags/{tag_id}
```

**Example:**

```bash
curl http://localhost:8321/api/v1/graph/tags/python
```

**Response:**

```json
{
  "id": "python",
  "memory_count": 12,
  "neighbors": ["testing", "backend", "flask", "fastapi"]
}
```

## Query Neighbors

Find all tags connected to a given tag within a specified depth.

```
GET /api/v1/graph/neighbors/{tag_id}?depth=2
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `depth` | integer | 1 | Maximum traversal depth |

**Example:**

```bash
# Direct neighbors only
curl http://localhost:8321/api/v1/graph/neighbors/python

# Neighbors up to 2 hops away
curl "http://localhost:8321/api/v1/graph/neighbors/python?depth=2"
```

**Response:**

```json
{
  "tag": "python",
  "depth": 2,
  "neighbors": [
    {"id": "testing", "distance": 1, "weight": 5},
    {"id": "pytest", "distance": 1, "weight": 3},
    {"id": "backend", "distance": 1, "weight": 4},
    {"id": "flask", "distance": 2, "weight": 2},
    {"id": "unit-testing", "distance": 2, "weight": 1}
  ]
}
```

## Find Shortest Path

Find the shortest path between two tags in the graph.

```
GET /api/v1/graph/path?from=X&to=Y
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | string | Yes | Source tag |
| `to` | string | Yes | Target tag |

**Example:**

```bash
curl "http://localhost:8321/api/v1/graph/path?from=python&to=machine-learning"
```

**Response:**

```json
{
  "from": "python",
  "to": "machine-learning",
  "path": ["python", "data-science", "machine-learning"],
  "length": 2
}
```

Returns a 404 if no path exists between the two tags.

## Export Full Graph

Export the complete graph structure for external analysis or visualization.

```
GET /api/v1/graph/export
```

**Example:**

```bash
curl http://localhost:8321/api/v1/graph/export
```

**Response:**

```json
{
  "nodes": [
    {"id": "python", "memory_count": 12},
    {"id": "testing", "memory_count": 8},
    {"id": "deployment", "memory_count": 5}
  ],
  "edges": [
    {"source": "python", "target": "testing", "weight": 5},
    {"source": "python", "target": "deployment", "weight": 3}
  ]
}
```
