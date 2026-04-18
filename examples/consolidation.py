"""
Memory Consolidation Example

Demonstrates the core hippocampus workflow:
1. Write raw memories to the hippocampus (working memory)
2. Trigger consolidation to organize them into long-term partitions
3. Observe the results

Prerequisites:
    pip install hippocampus-ai
    export HIPPOCAMPUS_LLM_API_KEY=your-key
    hippocampus init && hippocampus start
"""

import httpx
import time

BASE = "http://localhost:8321"


def main():
    client = httpx.Client(base_url=BASE)

    # 1. Write raw memories to hippocampus (working memory inbox)
    print("=== Writing working memories ===")
    raw_memories = [
        "The user said they love Vietnamese coffee",
        "Had a meeting about Q3 roadmap, decided to prioritize mobile",
        "Python's match statement is useful for pattern matching",
        "User asked to always respond in Chinese",
        "To deploy, run: docker compose up -d --build",
    ]

    for content in raw_memories:
        resp = client.post("/api/v1/memories", json={"content": content})
        print(f"  -> hippocampus: {content[:50]}")

    # 2. Check stats before consolidation
    print("\n=== Before Consolidation ===")
    stats = client.get("/api/v1/admin/stats").json()
    for p in stats["partitions"]:
        if p["memory_count"] > 0:
            print(f"  {p['name']}: {p['memory_count']} memories")

    # 3. Trigger consolidation
    print("\n=== Running Consolidation ===")
    resp = client.post("/api/v1/admin/consolidate")
    result = resp.json()
    print(f"  Processed: {result['processed']}")
    print(f"  Succeeded: {result['succeeded']}")
    print(f"  Failed: {result['failed']}")

    # 4. Check stats after consolidation
    print("\n=== After Consolidation ===")
    stats = client.get("/api/v1/admin/stats").json()
    for p in stats["partitions"]:
        if p["memory_count"] > 0:
            print(f"  {p['name']}: {p['memory_count']} memories")

    # 5. Check the knowledge graph
    print("\n=== Knowledge Graph Tags ===")
    tags = client.get("/api/v1/graph/tags").json()
    for tag in tags[:10]:
        print(f"  #{tag['id']} (weight: {tag['weight']}, memories: {len(tag['memory_ids'])})")

    # 6. Browse memories by partition
    for pid in ["mem_semantic", "mem_episodic", "mem_preference", "mem_procedural"]:
        resp = client.get("/api/v1/memories", params={"partition_id": pid})
        items = resp.json()["items"]
        if items:
            print(f"\n=== {pid} ===")
            for m in items:
                print(f"  [{m['importance_score']:.1f}] {m['content'][:60]} tags={m['tags']}")


if __name__ == "__main__":
    main()
