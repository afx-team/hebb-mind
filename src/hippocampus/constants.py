"""Memory partition types and system defaults."""

from enum import StrEnum


class PartitionType(StrEnum):
    HIPPOCAMPUS = "mem_hippocampus"
    SEMANTIC = "mem_semantic"
    EPISODIC = "mem_episodic"
    PREFERENCE = "mem_preference"
    PROCEDURAL = "mem_procedural"


DEFAULT_PARTITION = PartitionType.HIPPOCAMPUS

SYSTEM_PARTITIONS: set[PartitionType] = {
    PartitionType.HIPPOCAMPUS,
    PartitionType.SEMANTIC,
    PartitionType.EPISODIC,
    PartitionType.PREFERENCE,
    PartitionType.PROCEDURAL,
}

DEFAULT_PARTITION_DESCRIPTIONS: dict[PartitionType, str] = {
    PartitionType.HIPPOCAMPUS: "Working memory inbox. New memories arrive here before consolidation.",
    PartitionType.SEMANTIC: "Facts, knowledge, and general world information.",
    PartitionType.EPISODIC: "Experiences, events, and contextual interactions.",
    PartitionType.PREFERENCE: "User preferences, likes, dislikes, and personal settings.",
    PartitionType.PROCEDURAL: "Skills, how-to knowledge, and learned action patterns.",
}

DEFAULT_PARTITION_NAMES: dict[PartitionType, str] = {
    PartitionType.HIPPOCAMPUS: "Hippocampus",
    PartitionType.SEMANTIC: "Semantic Memory",
    PartitionType.EPISODIC: "Episodic Memory",
    PartitionType.PREFERENCE: "Preference Memory",
    PartitionType.PROCEDURAL: "Procedural Memory",
}
