from app.repositories.base import BaseRepository


class ClickHouseRepository(BaseRepository):
    def __init__(self, client, database: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__()
        self.client = client
        self.database = database

    def table(self, table_name: str) -> str:
        return f"{self.database}.{table_name}"

    def insert_model_rows(self, table_name: str, rows: list[object]) -> None:
        if not rows:
            return
        payload = [_clickhouse_row(row) for row in rows]
        columns = list(payload[0].keys())
        values = [[row[column] for column in columns] for row in payload]
        self.client.insert(self.table(table_name), values, column_names=columns)


def _clickhouse_row(row: object) -> dict[str, object]:
    if not hasattr(row, "model_dump"):
        raise TypeError("ClickHouse rows must be Pydantic models")
    payload = row.model_dump(mode="json")  # type: ignore[attr-defined]
    if "updated_at_replacing" in payload:
        payload["_updated_at"] = payload.pop("updated_at_replacing")
    return payload
