# Partitions API

Partitions organize memories into logical categories. Hippocampus ships with five built-in partitions and supports custom user-defined partitions.

## List Partitions

```
GET /api/v1/partitions
```

**Example:**

```bash
curl http://localhost:8321/api/v1/partitions
```

**Response:**

```json
[
  {
    "id": "mem_hippocampus",
    "name": "Hippocampus",
    "description": "Working memory inbox for unprocessed memories",
    "is_system": true
  },
  {
    "id": "mem_semantic",
    "name": "Semantic",
    "description": "Facts and knowledge",
    "is_system": true
  },
  {
    "id": "mem_episodic",
    "name": "Episodic",
    "description": "Events and history",
    "is_system": true
  },
  {
    "id": "mem_preference",
    "name": "Preference",
    "description": "Likes and dislikes",
    "is_system": true
  },
  {
    "id": "mem_procedural",
    "name": "Procedural",
    "description": "Skills and how-to knowledge",
    "is_system": true
  }
]
```

## Get Partition

```
GET /api/v1/partitions/{partition_id}
```

**Example:**

```bash
curl http://localhost:8321/api/v1/partitions/mem_semantic
```

## Create Partition

Create a custom partition.

```
POST /api/v1/partitions
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique partition ID (recommended prefix: `mem_`) |
| `name` | string | Yes | Display name |
| `description` | string | No | Partition description |

**Example:**

```bash
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "mem_project",
    "name": "Project Context",
    "description": "Current project knowledge and context"
  }'
```

## Update Partition

Update a partition's name or description.

```
PATCH /api/v1/partitions/{partition_id}
```

**Example:**

```bash
curl -X PATCH http://localhost:8321/api/v1/partitions/mem_project \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Project Knowledge",
    "description": "All project-related knowledge and context"
  }'
```

## Delete Partition

Delete a custom partition.

```
DELETE /api/v1/partitions/{partition_id}
```

**Example:**

```bash
curl -X DELETE http://localhost:8321/api/v1/partitions/mem_project
```

::: warning
System partitions (`mem_hippocampus`, `mem_semantic`, `mem_episodic`, `mem_preference`, `mem_procedural`) cannot be deleted. Attempting to delete a system partition will return a 400 error.
:::

## Built-in Partitions

| ID | Name | Purpose |
|----|------|---------|
| `mem_hippocampus` | Hippocampus | Working memory inbox; all new memories land here |
| `mem_semantic` | Semantic | Facts, knowledge, and general information |
| `mem_episodic` | Episodic | Events, interactions, and history |
| `mem_preference` | Preference | User likes, dislikes, and preferences |
| `mem_procedural` | Procedural | Skills, procedures, and how-to knowledge |
