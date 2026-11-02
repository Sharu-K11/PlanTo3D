
import os
from io import BytesIO
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_PATH = (
    BASE_DIR
    / "sketch_v1"
    / "checkpoints"
    / "sketch_model_v1.pth"
)


class SegmentationService:
    def __init__(self, model_path: Path | None = None):

        # Resolve checkpoint location
        self.model_path = Path(
            model_path
            if model_path is not None
            else os.getenv("MODEL_PATH", str(DEFAULT_MODEL_PATH))
        )

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Model checkpoint not found: {self.model_path}"
            )

        # Support CPU-only Docker or local CUDA
        device_name = os.getenv(
            "DEVICE",
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.device = torch.device(device_name)

        # Recreate training architecture
        self.model = smp.Unet(
            encoder_name="resnet18",
            encoder_weights=None,
            in_channels=3,
            classes=2,
            activation=None,
        ).to(self.device)

        # Load our trained weights
        state_dict = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=True,
        )

        self.model.load_state_dict(state_dict)
        self.model.eval()

        self.mean = torch.tensor(
            [0.485, 0.456, 0.406],
            device=self.device,
        ).view(1, 3, 1, 1)

        self.std = torch.tensor(
            [0.229, 0.224, 0.225],
            device=self.device,
        ).view(1, 3, 1, 1)

        print(
            f"Segmentation model loaded on {self.device} "
            f"from {self.model_path}"
        )

    def predict(self, image: Image.Image) -> bytes:

        original_size = image.size

        # Match training input dimensions
        image = image.convert("RGB").resize(
            (256, 256),
            Image.Resampling.BILINEAR,
        )

        array = np.asarray(image).copy()

        tensor = (
            torch.from_numpy(array)
            .permute(2, 0, 1)
            .float()
            .div(255.0)
            .unsqueeze(0)
            .to(self.device)
        )

        # Same normalization used during training
        tensor = (tensor - self.mean) / self.std

        # Inference without gradient tracking
        with torch.inference_mode():
            logits = self.model(tensor)
            prediction = logits.argmax(dim=1)[0]

        # Class 0 = black, class 1 = white
        mask_array = (
            prediction.cpu().numpy().astype(np.uint8) * 255
        )

        mask = Image.fromarray(mask_array).resize(
            original_size,
            Image.Resampling.NEAREST,
        )

        buffer = BytesIO()
        mask.save(buffer, format="PNG")

        return buffer.getvalue()
