from pydantic import BaseModel, ConfigDict, Field


class ImageUrlDetectRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"image_url": "https://example.com/image.jpg"}],
        }
    )

    image_url: str = Field(min_length=1)


class ImageBase64DetectRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD..."}],
        }
    )

    image_base64: str = Field(min_length=1)
