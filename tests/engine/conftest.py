"""Engine test fixtures.

Fully isolated from the legacy suite: its own in-memory database and fakes for
every external service (Places, LLM, embeddings). The root conftest's autouse
`clean_db` fixture targets the legacy Flask app, so it is overridden here.
"""
import hashlib

import numpy as np
import pytest

from engine.db import init_db, make_engine, make_session_factory


@pytest.fixture(autouse=True)
def clean_db():
    """Override the legacy autouse fixture: engine tests never touch the old app."""
    yield


@pytest.fixture()
def engine_db():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    session = make_session_factory(engine)()
    yield session
    session.close()
    engine.dispose()


class FakeEmbeddings:
    """Deterministic pseudo-embeddings: same text -> same unit vector."""
    dim = 16

    def embed(self, texts):
        out = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
            vec = np.random.default_rng(seed).standard_normal(self.dim).astype("float32")
            out.append(vec / np.linalg.norm(vec))
        return out


class FakePlaces:
    """Returns canned results per query; records calls."""

    def __init__(self, results=None):
        self.results = results or {}
        self.queries = []

    def search(self, query, lat, lng, radius_m=3000):
        self.queries.append(query)
        return list(self.results.get(query, []))


class FakeLLM:
    """Returns canned structured outputs; records calls."""

    def __init__(self, queries=None, tags=None):
        self.queries = queries or []
        self.tags = tags or []
        self.calls = []

    def generate_queries(self, *args, **kwargs):
        self.calls.append(("generate_queries", args, kwargs))
        return self.queries

    def extract_tags(self, *args, **kwargs):
        self.calls.append(("extract_tags", args, kwargs))
        return self.tags


@pytest.fixture()
def fake_embeddings():
    return FakeEmbeddings()


@pytest.fixture()
def fake_places():
    return FakePlaces()


@pytest.fixture()
def fake_llm():
    return FakeLLM()
