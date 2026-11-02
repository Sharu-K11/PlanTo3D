import asyncio
from io import BytesIO
from typing import Protocol

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from app.services.geometry_service import NoWallsDetectedError, mask_to_glb

router = APIRouter(
    tags=["Segmentation"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


class SegmentationService(Protocol):
    def predict(self, image: Image.Image) -> bytes:
        """Return the predicted wall mask encoded as PNG bytes."""
        ...


def _decode_png(image_bytes: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if img.format != "PNG":
                raise ValueError("Invalid PNG")

            if img.width * img.height > MAX_PIXELS:
                raise HTTPException(
                    status_code=413,
                    detail="Image dimensions too large",
                )

            return img.convert("RGB")

    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid PNG image",
        )


async def _predict_mask(request: Request, file: UploadFile) -> bytes:
    """Validate the uploaded PNG and return the predicted wall mask as PNG bytes."""
    try:
        service: SegmentationService | None = getattr(
            request.app.state, "segmentation_service", None
        )
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Segmentation model is not loaded",
            )

        if file.content_type != "image/png":
            raise HTTPException(
                status_code=400,
                detail="Only PNG images are supported",
            )

        image_bytes = await file.read(MAX_FILE_SIZE + 1)

        if len(image_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File exceeds 10 MB",
            )
    finally:
        await file.close()

    # Decoding and inference are CPU-bound; keep them off the event loop.
    image = await asyncio.to_thread(_decode_png, image_bytes)
    return await asyncio.to_thread(service.predict, image)


_UPLOAD_ERRORS = {
    400: {"description": "Not a valid PNG"},
    413: {"description": "File or image dimensions too large"},
    503: {"description": "Segmentation model not loaded"},
}


@router.post(
    "/segment",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "Predicted wall mask"},
        **_UPLOAD_ERRORS,
    },
)
async def segment_image(
    request: Request,
    file: UploadFile = File(...),
) -> Response:
    mask_bytes = await _predict_mask(request, file)
    return Response(
        content=mask_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="wall_mask.png"'
        },
    )


@router.post(
    "/generate-3d",
    response_class=Response,
    responses={
        200: {
            "content": {"model/gltf-binary": {}},
            "description": "Floor plan extruded into a 3D building (GLB, metres, Y up)",
        },
        **_UPLOAD_ERRORS,
        422: {"description": "No walls detected in the plan"},
    },
)
async def generate_3d(
    request: Request,
    file: UploadFile = File(...),
) -> Response:
    mask_bytes = await _predict_mask(request, file)
    try:
        glb_bytes = await asyncio.to_thread(mask_to_glb, mask_bytes)
    except NoWallsDetectedError as error:
        raise HTTPException(
            status_code=422, detail=str(error)
        ) from error

    return Response(
        content=glb_bytes,
        media_type="model/gltf-binary",
        headers={
            "Content-Disposition": 'attachment; filename="building.glb"'
        },
    )