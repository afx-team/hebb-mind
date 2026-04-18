"""
Partition Management Example

Demonstrates:
1. List system partitions
2. Create custom partitions
3. Update partition descriptions
4. Move memories between partitions
5. Delete custom partitions

Prerequisites:
    pip install hippocampus-ai
    hippocampus init && hippocampus start
"""

import httpx

BASE = "http://localhost:8321"


def main():
    client = httpx.Client(base_url=BASE)

    # 1. List system partitions
    print("=== System Partitions ===")
    resp = client.get("/api/v1/partitions")
    for p in resp.json():
        icon = "(*)" if p["is_system"] else "   "
        print(f"  {icon} {p['id']}: {p['name']} — {p['description'][:50]}")

    # 2. Create a custom partition
    print("\n=== Creating custom partition ===")
    resp = client.post("/api/v1/partitions", json={
        "id": "mem_project_alpha",
        "name": "Project Alpha",
        "description": "Knowledge specific to Project Alpha development",
    })
    print(f"  Created: {resp.json()['id']}")

    # 3. Store a memory in the custom partition
    resp = client.post("/api/v1/memories", json={
        "content": "Project Alpha uses React 19 with Server Components",
        "partition_id": "mem_project_alpha",
        "tags": ["react", "architecture"],
    })
    print(f"  Memory stored in custom partition: {resp.json()['id'][:8]}")

    # 4. Update partition description
    resp = client.patch("/api/v1/partitions/mem_project_alpha", json={
        "description": "Project Alpha — React 19 frontend, FastAPI backend",
    })
    print(f"  Updated description: {resp.json()['description']}")

    # 5. View memories in custom partition
    resp = client.get("/api/v1/memories", params={"partition_id": "mem_project_alpha"})
    print(f"\n=== Memories in Project Alpha: {resp.json()['total']} ===")
    for m in resp.json()["items"]:
        print(f"  {m['content'][:60]}")

    # 6. Delete custom partition (system partitions cannot be deleted)
    print("\n=== Cleanup ===")
    # Delete memory first
    for m in resp.json()["items"]:
        client.delete(f"/api/v1/memories/{m['id']}")
    # Delete partition
    resp = client.delete("/api/v1/partitions/mem_project_alpha")
    print(f"  Deleted mem_project_alpha: {resp.status_code == 204}")

    # Try deleting a system partition (should fail)
    resp = client.delete("/api/v1/partitions/mem_hippocampus")
    print(f"  Delete system partition: {resp.status_code} (expected 403)")


if __name__ == "__main__":
    main()
