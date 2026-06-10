from app.repositories.clickhouse.base import ClickHouseRepository
from app.schemas.clickhouse import VideoNsfwDetectionRow


class ClickHouseVideoResultRepository(ClickHouseRepository):
    def insert_rows(self, table_name: str, rows: list[VideoNsfwDetectionRow]) -> None:
        self.insert_model_rows(table_name, rows)
