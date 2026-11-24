import asyncio

from sqlalchemy import inspect

from engine.mcp_server import create_server
from engine.models import Base, Restaurant, User


def test_all_tables_created(engine_db):
    names = set(inspect(engine_db.get_bind()).get_table_names())
    assert names == set(Base.metadata.tables)
    assert {"users", "restaurants", "tags", "restaurant_tags", "user_tags",
            "outcomes", "outcome_tags", "requests", "predictions",
            "extraction_queue"} == names


def test_restaurant_stores_ids_only(engine_db):
    cols = {c.name for c in Restaurant.__table__.columns}
    for forbidden in ("name", "address", "rating", "hours", "reviews"):
        assert forbidden not in cols


def test_user_and_restaurant_roundtrip(engine_db):
    engine_db.add_all([User(external_id="u1"), Restaurant(place_id="p1")])
    engine_db.commit()
    assert engine_db.query(Restaurant).one().extraction_status == "none"


def test_mcp_server_lists_zero_tools():
    server = create_server()
    assert asyncio.run(server.list_tools()) == []


def test_fake_embeddings_are_deterministic(fake_embeddings):
    a, b = fake_embeddings.embed(["cozy", "cozy"])
    assert (a == b).all()
