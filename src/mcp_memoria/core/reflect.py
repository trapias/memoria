"""Reflect tool: LLM reasoning over memory.

Retrieves a broad set of relevant memories, then uses an LLM to
synthesize, analyze, compare, or build a timeline from them.
"""

import logging
from typing import Any, Literal

from mcp_memoria.core.memory_types import MemoryType, RecallResult

logger = logging.getLogger(__name__)

ReflectStyle = Literal["synthesis", "timeline", "comparison", "analysis"]
ReflectDepth = Literal["quick", "thorough", "deep"]

_DEPTH_LIMITS = {
    "quick": 5,
    "thorough": 15,
    "deep": 30,
}

_SYSTEM_PROMPT = """You are a memory analyst. You have access to a set of memories retrieved from a persistent knowledge base. Your job is to reason over these memories and provide useful insights.

Rules:
- Be concise and direct
- Reference specific memories when relevant (by their position number)
- If memories conflict, note the contradiction
- If information is sparse, say so honestly
- Respond in the same language as the user's query"""

_STYLE_INSTRUCTIONS = {
    "synthesis": "Synthesize these memories into a coherent summary. Identify key themes, patterns, and connections. Provide a unified understanding.",
    "timeline": "Organize these memories chronologically. Identify the sequence of events, decisions, and changes over time. Note any gaps in the timeline.",
    "comparison": "Compare and contrast the information in these memories. Identify agreements, contradictions, and different perspectives.",
    "analysis": "Analyze these memories critically. Identify patterns, root causes, implications, and actionable insights. What conclusions can be drawn?",
}


class Reflector:
    """Reasoning engine that synthesizes insights from retrieved memories."""

    def __init__(
        self,
        memory_manager: Any,
        embedder: Any,
        graph_manager: Any | None = None,
    ):
        self.memory_manager = memory_manager
        self.embedder = embedder
        self.graph_manager = graph_manager

    async def reflect(
        self,
        query: str,
        style: ReflectStyle = "synthesis",
        depth: ReflectDepth = "thorough",
        memory_types: list[MemoryType] | None = None,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Reflect on memories relevant to a query.

        Args:
            query: What to reflect about
            style: Reflection style (synthesis, timeline, comparison, analysis)
            depth: How many memories to consider (quick=5, thorough=15, deep=30)
            memory_types: Filter by memory types
            llm_model: Override LLM model for generation

        Returns:
            Dict with reflection text, sources count, and style used
        """
        limit = _DEPTH_LIMITS.get(depth, 15)

        # Broad recall to gather relevant memories
        results = await self.memory_manager.recall(
            query=query,
            memory_types=memory_types,
            limit=limit,
            min_score=0.3,  # Lower threshold for broader coverage
            hybrid=True,
            graph_manager=self.graph_manager,
        )

        if not results:
            return {
                "reflection": "No relevant memories found to reflect upon.",
                "sources": 0,
                "style": style,
                "depth": depth,
            }

        # Build memory context for LLM
        memory_context = self._format_memories(results)

        # Build the prompt
        style_instruction = _STYLE_INSTRUCTIONS[style]
        prompt = f"""## Query
{query}

## Instruction
{style_instruction}

## Retrieved Memories ({len(results)} total)
{memory_context}

## Your Reflection"""

        # Generate reflection using LLM
        try:
            reflection = await self.embedder.generate(
                prompt=prompt,
                model=llm_model,
                system=_SYSTEM_PROMPT,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "reflection": f"Reflection failed: could not generate LLM response. Error: {e}",
                "sources": len(results),
                "style": style,
                "depth": depth,
            }

        return {
            "reflection": reflection.strip(),
            "sources": len(results),
            "style": style,
            "depth": depth,
        }

    def _format_memories(self, results: list[RecallResult]) -> str:
        """Format recall results into a structured context for the LLM."""
        lines = []
        for i, r in enumerate(results, 1):
            mem = r.memory
            tags = ", ".join(mem.tags) if mem.tags else "none"
            date = mem.created_at.strftime("%Y-%m-%d") if mem.created_at else "unknown"
            lines.append(
                f"[{i}] [{mem.memory_type.value}] ({date}, importance: {mem.importance:.1f})\n"
                f"    Tags: {tags}\n"
                f"    {mem.content[:500]}"
            )
        return "\n\n".join(lines)
