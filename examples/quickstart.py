"""
Hippocampus Quick Start Example

Demonstrates the basic workflow:
1. Store memories via API
2. Search for related memories
3. View partition stats

Prerequisites:
    pip install afx-hippocampus
    hippocampus init && hippocampus start
"""

import httpx

BASE = "http://localhost:8321"


def main():
    client = httpx.Client(base_url=BASE)

    # 1. Store some memories
    print("=== Storing memories ===")
    memories = [
        {"content": "User prefers dark mode for all applications", "tags": ["preference", "ui"]},
        {"content": "Meeting with design team scheduled for Friday", "tags": ["event", "design"]},
        {"content": "Python 3.12 introduced type parameter syntax", "tags": ["python", "programming"]},
        {"content": "User is allergic to peanuts", "tags": ["health", "preference"], "importance_score": 9.0},
        {"content": "The project deadline is end of Q2 2026", "tags": ["project", "deadline"]},
    ]

    for mem in memories:
        resp = client.post("/api/v1/memories", json=mem)
        data = resp.json()
        print(f"  Created: [{data['id'][:8]}] {data['content'][:50]}")

    # 2. Search
    print("\n=== Searching for 'user preferences' ===")
    resp = client.post("/api/v1/search", json={"query": "user preferences", "top_k": 3})
    for result in resp.json():
        print(f"  Score: {result['score']:.3f} | {result['memory']['content'][:60]}")

    # 3. List memories by partition
    print("\n=== Memories in hippocampus (working memory) ===")
    resp = client.get("/api/v1/memories", params={"partition_id": "mem_hippocampus"})
    data = resp.json()
    print(f"  Total: {data['total']}")
    for item in data["items"][:5]:
        print(f"  [{item['id'][:8]}] {item['content'][:60]} tags={item['tags']}")

    # 4. View stats
    print("\n=== System Stats ===")
    resp = client.get("/api/v1/admin/stats")
    stats = resp.json()
    for p in stats["partitions"]:
        print(f"  {p['name']}: {p['memory_count']} memories")
    print(f"  Knowledge graph: {stats['graph']['tag_count']} tags, {stats['graph']['edge_count']} edges")
    print(f"  Scheduler: {'running' if stats['scheduler']['running'] else 'stopped'}")


if __name__ == "__main__":
    main()
