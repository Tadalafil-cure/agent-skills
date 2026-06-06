"""
Lightweight TF-IDF embedding for semantic fact retrieval.
Zero external dependencies — numpy only. Chinese-aware tokenization.

Usage:
    store = EmbeddingStore()
    vec = store.encode("记忆机制有问题吗")
    store.index_fact(fact_id, "holographic memory protocol 运行中")
    results = store.search("记忆机制", top_k=5)
      → [(fact_id, similarity_score), ...]
"""

from __future__ import annotations

import re
import math
from collections import Counter
from typing import Sequence

import numpy as np

# ── Tokenization ──────────────────────────────────────────────────────────

# Chinese character range
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
# Word split for non-CJK
_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text into unigrams + bigrams.

    Chinese: character-level unigrams and bigrams.
    English/numbers: word-level unigrams.
    """
    tokens: list[str] = []
    pos = 0
    for m in _CJK_RE.finditer(text):
        # Non-CJK before this block
        prefix = text[pos : m.start()]
        tokens.extend(_WORD_RE.findall(prefix.lower()))

        # CJK block: unigrams + bigrams
        block = m.group()
        tokens.extend(block)  # unigrams
        for i in range(len(block) - 1):
            tokens.append(block[i : i + 2])  # bigrams
        pos = m.end()

    # Trailing non-CJK
    suffix = text[pos:]
    tokens.extend(_WORD_RE.findall(suffix.lower()))

    return tokens


# ── Stopwords ─────────────────────────────────────────────────────────────

_STOPWORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "and", "but", "or", "if", "while", "that", "this",
    "it", "its", "he", "she", "they", "we", "you", "i", "me", "my",
    "your", "his", "her", "our", "their", "what", "which", "who",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "些", "所", "被", "把", "让", "向", "从", "对",
    "与", "及", "或", "但", "而", "且", "因", "为", "所以", "如果",
    "可以", "需要", "应该", "能够", "已经", "正在", "还是", "只是",
    "这个", "那个", "什么", "怎么", "怎样", "为什么", "这样", "那样",
    "吗", "呢", "吧", "啊", "哦", "嗯", "哈",
}


def _filter_tokens(tokens: list[str]) -> list[str]:
    """Filter stopwords and single-character non-informative tokens."""
    result = []
    for t in tokens:
        if t in _STOPWORDS:
            continue
        if len(t) == 1:
            # Keep only meaningful single CJK chars (skip punctuation etc)
            if '\u4e00' <= t <= '\u9fff':
                continue  # single CJK chars are too noisy
        result.append(t)
    return result


# ── Embedding Store ───────────────────────────────────────────────────────

class EmbeddingStore:
    """Builds and searches a semantic vector index over facts.

    Uses TF-IDF vectorization with cosine similarity. All computation is
    local (numpy), no API calls.
    """

    def __init__(self):
        self._vocab: dict[str, int] = {}   # token → column index
        self._idf: np.ndarray | None = None  # IDF values
        self._doc_count: int = 0
        self._fact_vectors: dict[int, np.ndarray] = {}  # fact_id → vector
        self._dirty: bool = False  # vocabulary needs rebuild

    # ── Encoding ───────────────────────────────────────────────────────

    def encode(self, text: str) -> np.ndarray:
        """Convert text to a TF vector (dense, vocab-sized)."""
        tokens = _filter_tokens(tokenize(text))
        if not tokens or not self._vocab:
            return np.zeros(max(1, len(self._vocab)), dtype=np.float32)

        tf = Counter(tokens)
        vec = np.zeros(len(self._vocab), dtype=np.float32)
        for token, count in tf.items():
            idx = self._vocab.get(token)
            if idx is not None:
                vec[idx] = count
        return vec

    def _as_tfidf(self, tf_vec: np.ndarray) -> np.ndarray:
        """Convert TF vector to TF-IDF using stored IDF values."""
        if self._idf is None or len(self._idf) != len(tf_vec):
            return tf_vec
        return tf_vec * self._idf

    # ── Indexing ───────────────────────────────────────────────────────

    def index_fact(self, fact_id: int, content: str) -> np.ndarray:
        """Add or update a fact's vector. Returns the stored vector.

        If new tokens are discovered, marks the vocabulary as dirty
        (caller should rebuild).
        """
        tokens = _filter_tokens(tokenize(content))
        if not tokens:
            vec = np.zeros(max(1, len(self._vocab)), dtype=np.float32)
            self._fact_vectors[fact_id] = vec
            return vec

        new_tokens = set(tokens) - set(self._vocab)
        if new_tokens:
            self._dirty = True
            # Extend vocabulary inline for now
            for token in new_tokens:
                if token not in self._vocab:
                    self._vocab[token] = len(self._vocab)

        # Rebuild vector with potentially extended vocab
        tf = Counter(tokens)
        vec = np.zeros(len(self._vocab), dtype=np.float32)
        for token, count in tf.items():
            idx = self._vocab.get(token)
            if idx is not None:
                vec[idx] = count

        self._fact_vectors[fact_id] = vec
        self._doc_count = max(self._doc_count, len(self._fact_vectors))
        return vec

    def rebuild_idf(self) -> None:
        """Rebuild IDF values from all indexed facts."""
        if not self._fact_vectors:
            self._idf = None
            return

        n = len(self._fact_vectors)
        vocab_size = len(self._vocab)

        # Pad all vectors to same length
        padded = []
        for vec in self._fact_vectors.values():
            if len(vec) < vocab_size:
                vec = np.pad(vec, (0, vocab_size - len(vec)))
            padded.append(vec[:vocab_size])

        # Count document frequency for each term
        df = np.zeros(vocab_size, dtype=np.float32)
        for vec in padded:
            df += (vec > 0).astype(np.float32)

        # Smooth IDF: log((N + 1) / (df + 1)) + 1
        self._idf = np.log((n + 1) / (df + 1)) + 1.0
        self._dirty = False

    def remove_fact(self, fact_id: int) -> None:
        """Remove a fact from the index."""
        self._fact_vectors.pop(fact_id, None)
        self._dirty = True

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self, query: str, top_k: int = 10,
        trust_scores: dict[int, float] | None = None,
    ) -> list[tuple[int, float]]:
        """Search for facts semantically similar to query.

        Returns list of (fact_id, score) sorted by score descending.
        Score = cosine_similarity * trust_score (if provided).
        """
        if not self._fact_vectors or not self._vocab:
            return []

        q_vec = self.encode(query)
        q_tfidf = self._as_tfidf(q_vec)
        q_norm = np.linalg.norm(q_tfidf)
        if q_norm < 1e-8:
            return []

        results = []
        vocab_size = len(self._vocab)
        for fid, f_vec in self._fact_vectors.items():
            # Align vector size (vocab may have grown)
            if len(f_vec) < vocab_size:
                f_vec = np.pad(f_vec, (0, vocab_size - len(f_vec)))
            f_vec = f_vec[:vocab_size]
            f_tfidf = self._as_tfidf(f_vec)
            f_norm = np.linalg.norm(f_tfidf)
            if f_norm < 1e-8:
                continue

            cosine = float(np.dot(q_tfidf, f_tfidf) / (q_norm * f_norm))
            score = cosine
            if trust_scores:
                trust = trust_scores.get(fid, 0.5)
                score *= trust

            results.append((fid, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # ── Serialization ──────────────────────────────────────────────────

    def vector_to_bytes(self, vec: np.ndarray) -> bytes:
        """Serialize vector for SQLite BLOB storage."""
        return vec.astype(np.float32).tobytes()

    def bytes_to_vector(self, data: bytes) -> np.ndarray:
        """Deserialize vector from SQLite BLOB."""
        return np.frombuffer(data, dtype=np.float32)

    def __len__(self) -> int:
        return len(self._fact_vectors)
