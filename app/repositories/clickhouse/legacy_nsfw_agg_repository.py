from app.repositories.clickhouse.base import ClickHouseRepository
from app.schemas.legacy import LegacyNsfwAggRow


class ClickHouseLegacyNsfwAggRepository(ClickHouseRepository):
    def insert_rows(self, table_name: str, rows: list[LegacyNsfwAggRow]) -> None:
        self.insert_model_rows(table_name, rows)
