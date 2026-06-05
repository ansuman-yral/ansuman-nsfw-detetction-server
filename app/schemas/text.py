from pydantic import BaseModel, ConfigDict, Field


class TextDetectRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"text": "A cinematic dance video on a beach at sunset."}],
        }
    )

    text: str = Field(min_length=1)
