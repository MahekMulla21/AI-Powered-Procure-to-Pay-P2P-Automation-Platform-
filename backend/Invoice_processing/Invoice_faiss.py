# Invoice_faiss.py
import sys
from pathlib import Path
# ─────────────────────────────────────────────────────────────────
# FAISS-Style Semantic Search Layer (pure numpy — no ML libraries)
#
# Implements:
#   • TF-IDF vectorisation with unigram + bigram tokens
#   • Cosine similarity search via L2-normalised dot product
#   • chunk_text()  – splits raw OCR text into overlapping windows
#   • TF_IDF_FAISS  – index class with build + search
#
# This is a drop-in substitute for the faiss-cpu library when that
# library is unavailable (e.g. air-gapped or restricted environments).
# ─────────────────────────────────────────────────────────────────

import numpy as np

from Invoice_config.Invoice_config import CHUNK_SIZE, CHUNK_OVERLAP, FAISS_TOP_K


# ── Text chunking ─────────────────────────────────────────────────

def chunk_text(
    text      : str,
    chunk_size: int = CHUNK_SIZE,
    overlap   : int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Split raw text into overlapping word-level windows.

    Args:
        text       : Full OCR-extracted text.
        chunk_size : Number of words per chunk.
        overlap    : Number of words shared between consecutive chunks.

    Returns:
        List of non-empty chunk strings.
    """
    words  = text.split()
    step   = max(1, chunk_size - overlap)
    chunks = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ── TF-IDF FAISS index ────────────────────────────────────────────

class TF_IDF_FAISS:
    """
    Lightweight semantic search index built on TF-IDF + cosine similarity.

    Usage:
        index = TF_IDF_FAISS(chunks)
        results = index.search("bank payment IFSC", top_k=3)
        # → [(score, chunk_text), ...]
    """

    def __init__(self, chunks: list[str]):
        self.chunks    : list[str]       = chunks
        self.vocab     : dict[str, int]  = {}
        self.idf       : np.ndarray      = None   # shape (V,)
        self.tfidf_mat : np.ndarray      = None   # shape (N, V), L2-normalised
        self._build_index()

    # ── Tokenisation ─────────────────────────────────────────────

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """
        Produce unigrams + bigrams from lowercased text.
        No regex — uses str.split() and f-string concatenation.
        """
        tokens   = text.lower().split()
        unigrams = tokens
        bigrams  = [
            f"{tokens[i]}_{tokens[i + 1]}"
            for i in range(len(tokens) - 1)
        ]
        return unigrams + bigrams

    # ── Index construction ────────────────────────────────────────

    def _build_index(self) -> None:
        """Build TF-IDF matrix and IDF vector from self.chunks."""
        tokenised = [self._tokenise(c) for c in self.chunks]

        # Vocabulary: sorted for determinism
        all_terms  = {t for toks in tokenised for t in toks}
        self.vocab = {term: idx for idx, term in enumerate(sorted(all_terms))}

        N = len(self.chunks)
        V = len(self.vocab)

        # ── Term-Frequency matrix (N × V) ────────────────────────
        tf_mat = np.zeros((N, V), dtype=np.float32)
        for i, toks in enumerate(tokenised):
            for t in toks:
                if t in self.vocab:
                    tf_mat[i, self.vocab[t]] += 1
            row_sum = tf_mat[i].sum()
            if row_sum > 0:
                tf_mat[i] /= row_sum    # normalise: relative term frequency

        # ── Inverse Document Frequency vector (V,) ───────────────
        df       = np.count_nonzero(tf_mat, axis=0).astype(np.float32)
        self.idf = np.log((N + 1) / (df + 1)) + 1   # smoothed IDF (sklearn style)

        # ── TF-IDF matrix ─────────────────────────────────────────
        self.tfidf_mat = tf_mat * self.idf

        # ── L2 normalisation for cosine via dot product ───────────
        norms = np.linalg.norm(self.tfidf_mat, axis=1, keepdims=True)
        norms[norms == 0] = 1                         # avoid division by zero
        self.tfidf_mat /= norms

    # ── Query ────────────────────────────────────────────────────

    def search(
        self,
        query : str,
        top_k : int = FAISS_TOP_K,
    ) -> list[tuple[float, str]]:
        """
        Return the top-k chunks most semantically similar to query.

        Args:
            query : Natural-language search string.
            top_k : Number of results to return.

        Returns:
            List of (cosine_score, chunk_text) tuples, highest score first.
        """
        q_tokens = self._tokenise(query)
        V        = len(self.vocab)
        q_vec    = np.zeros(V, dtype=np.float32)

        for t in q_tokens:
            if t in self.vocab:
                q_vec[self.vocab[t]] += 1

        if q_vec.sum() > 0:
            q_vec  = q_vec * self.idf
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec /= q_norm

        scores  = self.tfidf_mat @ q_vec                    # cosine similarities
        top_idx = np.argsort(scores)[::-1][:top_k]

        return [(float(scores[i]), self.chunks[i]) for i in top_idx]
