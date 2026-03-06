import hashlib
from typing import List
from dataclasses import dataclass, field


@dataclass
class ContextSegment:
    id: str
    content: str


@dataclass
class Context:
    segments: List[ContextSegment]


@dataclass
class ContextDelta:
    changed_segments: List[ContextSegment] = field(default_factory=list)

    def add_changed_segment(self, segment: ContextSegment):
        self.changed_segments.append(segment)


class ContextDiffer:
    def __init__(self):
        self.hashes = {}  # conversation_id -> {segment_id -> hash}

    async def compute_delta(self, conversation_id: str, new_context: Context) -> ContextDelta:
        delta = ContextDelta()
        if conversation_id not in self.hashes:
            self.hashes[conversation_id] = {}

        for segment in new_context.segments:
            segment_hash = hashlib.blake2b(segment.content.encode()).hexdigest()[:16]
            if self._has_changed(conversation_id, segment.id, segment_hash):
                delta.add_changed_segment(segment)
                self._update_hash(conversation_id, segment.id, segment_hash)
        return delta

    def _has_changed(self, conversation_id: str, segment_id: str, segment_hash: str) -> bool:
        return self.hashes.get(conversation_id, {}).get(segment_id) != segment_hash

    def _update_hash(self, conversation_id: str, segment_id: str, segment_hash: str):
        if conversation_id not in self.hashes:
            self.hashes[conversation_id] = {}
        self.hashes[conversation_id][segment_id] = segment_hash
