import sqlite3

from app.api.common import execute


def test_sqlite_parameter_binding_preserves_prefix_names(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE sample (id TEXT, monetization TEXT, monetization_score REAL)")

    execute(
        connection,
        "INSERT INTO sample(id, monetization, monetization_score) VALUES (:id, :monetization, :monetization_score)",
        {"id": "1", "monetization": "ads", "monetization_score": 8.5},
    )

    row = connection.execute("SELECT id, monetization, monetization_score FROM sample").fetchone()
    assert row == ("1", "ads", 8.5)
    connection.close()
