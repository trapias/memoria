"""Prompt templates for memory operations."""

from typing import Any


class PromptTemplates:
    """Collection of prompt templates for memory operations."""

    RECALL_CONTEXT = """Based on the following memories, provide relevant context:

{memories}

User query: {query}

Provide a concise summary of the relevant information."""

    SUMMARIZE_MEMORIES = """Summarize the following memories into a coherent narrative:

{memories}

Focus on key facts, decisions, and their relationships."""

    EXTRACT_FACTS = """Extract key facts from the following content that should be remembered:

Content:
{content}

List each fact as a separate item that can be stored independently."""

    CONSOLIDATE_PROMPT = """The following memories appear to be related or similar:

{memories}

Create a single consolidated memory that preserves all important information."""

    RELATE_MEMORIES = """Analyze the relationships between these memories:

{memories}

Identify:
1. Cause-effect relationships
2. Temporal sequences
3. Conceptual connections
4. Contradictions or updates"""

    @classmethod
    def format_memories_for_prompt(
        cls,
        memories: list[dict[str, Any]],
        include_metadata: bool = True,
    ) -> str:
        """Format memories for inclusion in a prompt.

        Args:
            memories: List of memory dicts
            include_metadata: Include tags, dates, etc.

        Returns:
            Formatted string
        """
        formatted = []

        for i, mem in enumerate(memories, 1):
            entry = [f"{i}. {mem.get('content', '')}"]

            if include_metadata:
                if mem.get("tags"):
                    entry.append(f"   Tags: {', '.join(mem['tags'])}")
                if mem.get("created_at"):
                    entry.append(f"   Date: {mem['created_at']}")
                if mem.get("importance"):
                    entry.append(f"   Importance: {mem['importance']:.2f}")

            formatted.append("\n".join(entry))

        return "\n\n".join(formatted)

    @classmethod
    def recall_context(cls, memories: list[dict[str, Any]], query: str) -> str:
        """Generate a recall context prompt.

        Args:
            memories: Retrieved memories
            query: User query

        Returns:
            Formatted prompt
        """
        return cls.RECALL_CONTEXT.format(
            memories=cls.format_memories_for_prompt(memories),
            query=query,
        )

    @classmethod
    def summarize(cls, memories: list[dict[str, Any]]) -> str:
        """Generate a summarization prompt.

        Args:
            memories: Memories to summarize

        Returns:
            Formatted prompt
        """
        return cls.SUMMARIZE_MEMORIES.format(
            memories=cls.format_memories_for_prompt(memories),
        )

    @classmethod
    def extract_facts(cls, content: str) -> str:
        """Generate a fact extraction prompt.

        Args:
            content: Content to extract facts from

        Returns:
            Formatted prompt
        """
        return cls.EXTRACT_FACTS.format(content=content)

    @classmethod
    def consolidate(cls, memories: list[dict[str, Any]]) -> str:
        """Generate a consolidation prompt.

        Args:
            memories: Similar memories to consolidate

        Returns:
            Formatted prompt
        """
        return cls.CONSOLIDATE_PROMPT.format(
            memories=cls.format_memories_for_prompt(memories),
        )

    @classmethod
    def relate(cls, memories: list[dict[str, Any]]) -> str:
        """Generate a relationship analysis prompt.

        Args:
            memories: Memories to analyze

        Returns:
            Formatted prompt
        """
        return cls.RELATE_MEMORIES.format(
            memories=cls.format_memories_for_prompt(memories),
        )
