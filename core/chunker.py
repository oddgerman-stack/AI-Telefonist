import re
from typing import Generator, List
from core.config import config

class StreamChunker:
    """
    Sentence & Clause Chunker for low-latency streaming Speech-to-Speech cascade.
    Splits LLM token streams on natural pause boundaries (clauses, punctuation)
    to enable sub-100ms TTS chunk synthesis without waiting for the full LLM completion.
    """

    def __init__(self):
        self.delimiters = config.get("pipeline.chunker.delimiters", [".", "?", "!", ",", ";", "\n", "—", ":"])
        self.min_tokens = config.get("pipeline.chunker.min_tokens", 3)
        self.max_tokens = config.get("pipeline.chunker.max_tokens", 25)
        
        # Regex to prevent splitting on common abbreviations like B.V., dhr., mw., nr., e.g., i.e.
        self.abbrev_regex = re.compile(r'\b(b\.v|dhr|mw|dr|prof|bijv|nr|ca|jl|e\.g|i\.e)\.$', re.IGNORECASE)

    def chunk_tokens(self, token_generator: Generator[str, None, None]) -> Generator[str, None, None]:
        """
        Takes a streaming token generator from the LLM and yields synthesized-ready phrases.
        """
        buffer = ""
        token_count = 0

        for token in token_generator:
            buffer += token
            token_count += len(token.strip().split())

            # Check if any delimiter is hit
            if self._should_split(buffer, token_count):
                clean_chunk = buffer.strip()
                if clean_chunk:
                    yield clean_chunk
                buffer = ""
                token_count = 0

        # Flush any remaining text in buffer
        if buffer.strip():
            yield buffer.strip()

    def _should_split(self, text: str, token_count: int) -> bool:
        """Determines if the current buffered text represents a natural speech chunk."""
        if not text:
            return False

        stripped = text.rstrip()
        if not stripped:
            return False

        last_char = stripped[-1]

        # Forced split if chunk is getting too long
        if token_count >= self.max_tokens:
            return True

        # Check if last character is a delimiter and we meet minimum token threshold
        if last_char in self.delimiters and token_count >= self.min_tokens:
            # Check for abbreviations
            if last_char == "." and self.abbrev_regex.search(stripped):
                return False
            return True

        return False
