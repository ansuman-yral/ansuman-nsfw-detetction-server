from app.repositories.clickhouse.base import ClickHouseRepository
from app.schemas.storage_action import StorageActionRow


class ClickHouseStorageActionRepository(ClickHouseRepository):
    def insert_rows(self, table_name: str, rows: list[StorageActionRow]) -> None:
        self.insert_model_rows(table_name, rows)
