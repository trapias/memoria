"""Observation Consolidation: generate higher-level insights from memory clusters.

Finds clusters of semantically similar memories, then uses LLM to
synthesize each cluster into a concise observation. Observations are
stored as new semantic memories and linked to their source facts via
the 'derives' relation in the knowledge graph.
"""

import logging
from typing import Any

from mcp_memoria.core.memory_types import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

_OBSERVATION_SYSTEM = """You are a knowledge analyst. Given a cluster of related memories, synthesize them into a single, concise observation that captures the higher-level insight.

Rules:
- Be concise (1-3 sentences)
- Capture the common pattern or overarching insight
- Don't just list the facts — extract the meaning
- If facts contradict each other, note the tension
- Respond in the same language as the majority of the input memories"""

_OBSERVATION_PROMPT = """## Related Memories (Cluster of {count})

{memories}

## Task
Synthesize these {count} related memories into ONE concise observation (1-3 sentences) that captures the higher-level insight or pattern. What do these facts collectively tell us?

## Observation"""


class ObservationCluster:
    """A cluster of similar memories with a potential observation."""

    def __init__(self, seed: MemoryItem, members: list[MemoryItem], similarity: float):
        self.seed = seed
        self.members = members  # includes seed
        self.similarity = similarity
        self.observation: str | None = None

    @property
    def member_ids(self) -> list[str]:
        return [m.id for m in self.members]

    def __len__(self) -> int:
        return len(self.members)


class ObservationConsolidator:
    """Generates observations from clusters of similar memories."""

    def __init__(
        self,
        memory_manager: Any,
        embedder: Any,
        graph_manager: Any | None = None,
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 3,
    ):
        self.memory_manager = memory_manager
        self.embedder = embedder
        self.graph_manager = graph_manager
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

    async def find_clusters(
        self,
        memory_type: MemoryType | None = None,
        limit: int = 100,
    ) -> list[ObservationCluster]:
        """Find clusters of similar memories.

        Scans memories and groups those above the similarity threshold
        into clusters. Each memory appears in at most one cluster.

        Args:
            memory_type: Filter by type (default: semantic only)
            limit: Max memories to scan

        Returns:
            List of ObservationClusters with 3+ members
        """
        target_type = memory_type or MemoryType.SEMANTIC
        collections = [target_type.value]

        # Fetch all memories with their vectors
        all_memories: list[tuple[MemoryItem, list[float]]] = []
        for collection in collections:
            results, _ = await self.memory_manager.vector_store.scroll(
                collection=collection,
                limit=limit,
                with_vectors=True,
                filter_conditions={"chunk_index": 0} if True else None,
            )
            for r in results:
                parent_id = r.payload.get("parent_id", r.id)
                if r.payload.get("chunk_index", 0) == 0 and r.vector:
                    mem = MemoryItem.from_payload(parent_id, r.payload)
                    all_memories.append((mem, r.vector))

        if len(all_memories) < self.min_cluster_size:
            return []

        # Simple greedy clustering
        used = set()
        clusters = []

        for i, (seed_mem, seed_vec) in enumerate(all_memories):
            if seed_mem.id in used:
                continue

            # Find similar memories to this seed
            members = [seed_mem]
            for j, (cand_mem, cand_vec) in enumerate(all_memories):
                if i == j or cand_mem.id in used:
                    continue
                sim = self._cosine_similarity(seed_vec, cand_vec)
                if sim >= self.similarity_threshold:
                    members.append(cand_mem)

            if len(members) >= self.min_cluster_size:
                avg_sim = self.similarity_threshold  # Approximate
                cluster = ObservationCluster(
                    seed=seed_mem, members=members, similarity=avg_sim
                )
                clusters.append(cluster)
                used.update(m.id for m in members)

        logger.info(f"Found {len(clusters)} clusters from {len(all_memories)} memories")
        return clusters

    async def generate_observations(
        self,
        clusters: list[ObservationCluster] | None = None,
        memory_type: MemoryType | None = None,
        dry_run: bool = True,
        llm_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generate observations from memory clusters.

        Args:
            clusters: Pre-computed clusters (if None, will find them)
            memory_type: Memory type to scan for clusters
            dry_run: If True, generate but don't store observations
            llm_model: Override LLM model

        Returns:
            List of observation dicts with cluster info and generated text
        """
        if clusters is None:
            clusters = await self.find_clusters(memory_type=memory_type)

        if not clusters:
            return []

        observations = []
        for cluster in clusters:
            # Format cluster memories for LLM
            mem_text = "\n\n".join(
                f"- [{m.memory_type.value}] (importance: {m.importance:.1f}) {m.content[:300]}"
                for m in cluster.members
            )

            prompt = _OBSERVATION_PROMPT.format(
                count=len(cluster),
                memories=mem_text,
            )

            try:
                observation_text = await self.embedder.generate(
                    prompt=prompt,
                    model=llm_model,
                    system=_OBSERVATION_SYSTEM,
                    temperature=0.3,
                )
                cluster.observation = observation_text.strip()
            except Exception as e:
                logger.error(f"Failed to generate observation for cluster: {e}")
                cluster.observation = None
                continue

            obs_result = {
                "observation": cluster.observation,
                "source_count": len(cluster),
                "source_ids": cluster.member_ids,
                "stored": False,
                "observation_id": None,
            }

            # Store if not dry_run
            if not dry_run and cluster.observation:
                stored = await self._store_observation(cluster)
                if stored:
                    obs_result["stored"] = True
                    obs_result["observation_id"] = stored

            observations.append(obs_result)

        return observations

    async def _store_observation(self, cluster: ObservationCluster) -> str | None:
        """Store an observation as a new semantic memory and link to sources.

        Returns:
            Observation memory ID if successful, None otherwise
        """
        if not cluster.observation:
            return None

        try:
            # Store as semantic memory with special tag
            obs_memory = await self.memory_manager.store(
                content=cluster.observation,
                memory_type=MemoryType.SEMANTIC,
                tags=["observation", "auto-generated"],
                importance=0.7,
                metadata={"source_count": len(cluster), "is_observation": True},
            )

            # Link to source memories via 'derives' relation
            if self.graph_manager:
                for source_mem in cluster.members:
                    try:
                        await self.graph_manager.add_relation(
                            source_id=obs_memory.id,
                            target_id=source_mem.id,
                            relation_type="derives",
                            weight=cluster.similarity,
                            metadata={"auto_generated": True},
                        )
                    except Exception as e:
                        logger.warning(f"Failed to link observation to {source_mem.id}: {e}")

            return obs_memory.id

        except Exception as e:
            logger.error(f"Failed to store observation: {e}")
            return None

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
