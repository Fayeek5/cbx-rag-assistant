"""Embedding model behaviour (uses the real bge-small model, cached locally)."""
from __future__ import annotations

import math

from app.embeddings import embed_passages, embed_query


def test_passage_embeddings_shape_and_count():
    vecs = embed_passages(["hello world", "another passage"])
    assert len(vecs) == 2
    assert len(vecs[0]) == len(vecs[1]) > 0  # consistent dimensionality


def test_query_embedding_is_normalized():
    v = embed_query("what is a codelist field?")
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-2  # normalize_embeddings=True


def test_query_and_passage_same_dim():
    q = embed_query("hello")
    p = embed_passages(["hello"])[0]
    assert len(q) == len(p)


def test_similar_texts_closer_than_dissimilar():
    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))
    q = embed_query("how do I fix a 401 unauthorized error")
    near = embed_passages(["A 401 means your token expired; request a new one."])[0]
    far = embed_passages(["The packing carton dimensions are measured in cm."])[0]
    assert cos(q, near) > cos(q, far)
