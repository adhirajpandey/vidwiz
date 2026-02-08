
import pytest

import src.database as database


def test_get_db_closes_session(monkeypatch):
    closed = {"flag": False}

    class _FakeSession:
        def close(self):
            closed["flag"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: _FakeSession())
    gen = database.get_db()
    session = next(gen)
    assert isinstance(session, _FakeSession)
    with pytest.raises(StopIteration):
        next(gen)
    assert closed["flag"] is True
