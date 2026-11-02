import asyncio
import io
import unittest
from pathlib import Path

import support  # noqa: F401  # isort: skip  # must run before app imports

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app, load_segmentation_service
from app.routers.segmentation import MAX_FILE_SIZE

URL = "/api/v1/segment"


def png_bytes(width: int = 16, height: int = 8, mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeSegmentationService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, int]]] = []

    def predict(self, image: Image.Image) -> bytes:
        self.calls.append((image.mode, image.size))
        return png_bytes(image.width, image.height, mode="L")


class SegmentationLoaderTests(unittest.TestCase):
    def test_disabled_returns_none(self) -> None:
        config = get_settings().model_copy(update={"segmentation_enabled": False})
        self.assertIsNone(asyncio.run(load_segmentation_service(config)))

    def test_missing_weights_returns_none(self) -> None:
        config = get_settings().model_copy(
            update={
                "segmentation_enabled": True,
                "segmentation_model_path": Path("does/not/exist.pth"),
            }
        )
        with self.assertLogs("uvicorn.error", level="WARNING") as logs:
            self.assertIsNone(asyncio.run(load_segmentation_service(config)))
        self.assertIn("weights not found", logs.output[0])


class SegmentationWithoutModelTests(unittest.TestCase):
    def test_returns_503_when_model_not_loaded(self) -> None:
        with TestClient(app) as client:
            response = client.post(URL, files={"file": ("plan.png", png_bytes(), "image/png")})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Segmentation model is not loaded")


class SegmentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app).__enter__()
        self.service = FakeSegmentationService()
        app.state.segmentation_service = self.service

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def post(self, data: bytes, content_type: str = "image/png", name: str = "plan.png"):
        return self.client.post(URL, files={"file": (name, data, content_type)})

    def test_returns_mask_png(self) -> None:
        response = self.post(png_bytes(40, 20))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(
            response.headers["content-disposition"], 'inline; filename="wall_mask.png"'
        )
        with Image.open(io.BytesIO(response.content)) as mask:
            self.assertEqual(mask.size, (40, 20))
        self.assertEqual(self.service.calls, [("RGB", (40, 20))])

    def test_converts_rgba_input_to_rgb(self) -> None:
        response = self.post(png_bytes(4, 4, mode="RGBA"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.service.calls, [("RGB", (4, 4))])

    def test_rejects_non_png_content_type(self) -> None:
        response = self.post(png_bytes(), content_type="image/jpeg")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only PNG images are supported")
        self.assertEqual(self.service.calls, [])

    def test_rejects_invalid_png_bytes(self) -> None:
        response = self.post(b"definitely not a png")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid PNG image")

    def test_rejects_other_image_format_labelled_png(self) -> None:
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buffer, format="JPEG")
        response = self.post(buffer.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid PNG image")

    def test_rejects_file_over_10_mb(self) -> None:
        response = self.post(png_bytes() + b"\x00" * MAX_FILE_SIZE)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "File exceeds 10 MB")
        self.assertEqual(self.service.calls, [])

    def test_rejects_too_many_pixels(self) -> None:
        # 5000 x 5000 = 25M pixels > 20M limit, but compresses to a small file.
        response = self.post(png_bytes(5000, 5000, mode="1"))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "Image dimensions too large")
        self.assertEqual(self.service.calls, [])


if __name__ == "__main__":
    unittest.main()
