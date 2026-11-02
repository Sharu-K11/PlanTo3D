"""Real-model tests. Skipped unless requirements-ml.txt is installed and weights exist."""

import importlib.util
import io
import unittest

import support  # noqa: F401  # isort: skip  # must run before app imports

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import get_settings
from app.main import app

WEIGHTS = get_settings().segmentation_model_path
HAS_ML = all(importlib.util.find_spec(m) for m in ("torch", "segmentation_models_pytorch", "numpy"))


@unittest.skipUnless(HAS_ML and WEIGHTS.is_file(), "needs requirements-ml.txt and model weights")
class RealSegmentationModelTests(unittest.TestCase):
    service = None

    @classmethod
    def setUpClass(cls) -> None:
        from app.services.segmentation_service import SegmentationService

        cls.service = SegmentationService(WEIGHTS)

    def floor_plan(self, width: int = 300, height: int = 200) -> bytes:
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, width - 20, height - 20), outline="black", width=6)
        draw.line((width // 2, 20, width // 2, height - 20), fill="black", width=6)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_endpoint_returns_binary_mask_at_input_size(self) -> None:
        with TestClient(app) as client:
            app.state.segmentation_service = self.service
            response = client.post(
                "/api/v1/segment",
                files={"file": ("plan.png", self.floor_plan(), "image/png")},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "image/png")
        with Image.open(io.BytesIO(response.content)) as mask:
            self.assertEqual(mask.size, (300, 200))
            self.assertEqual(mask.mode, "L")
            self.assertLessEqual(set(mask.tobytes()), {0, 255})


if __name__ == "__main__":
    unittest.main()
