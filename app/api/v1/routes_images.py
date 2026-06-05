from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_image_detection_service
from app.schemas.image import ImageBase64DetectRequest, ImageUrlDetectRequest
from app.services.image_detection_service import ImageDetectionService

router = APIRouter(prefix="/images", tags=["images"])
ImageServiceDep = Annotated[ImageDetectionService, Depends(get_image_detection_service)]


@router.post(
    "/detect-url",
    summary="Classify an image URL",
    description=(
        "Protected stateless endpoint. Downloads/classifies one image URL through the configured GPU model. "
        "It does not write PostgreSQL, ClickHouse, KVRocks, or storage state."
    ),
)
async def detect_image_url(
    request: ImageUrlDetectRequest,
    image_service: ImageServiceDep,
) -> dict[str, object]:
    return await image_service.detect_url(request.image_url)


@router.post(
    "/detect-base64",
    summary="Classify a base64 image",
    description=(
        "Protected stateless endpoint. Classifies one base64-encoded image through the configured GPU model. "
        "It does not write PostgreSQL, ClickHouse, KVRocks, or storage state."
    ),
)
async def detect_image_base64(
    request: ImageBase64DetectRequest,
    image_service: ImageServiceDep,
) -> dict[str, object]:
    return await image_service.detect_base64(request.image_base64)
