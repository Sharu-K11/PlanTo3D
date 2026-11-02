
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


BASE_DIR = Path(__file__).resolve().parent


class SketchDataset(Dataset):
    def __init__(self):
        self.image_dir = BASE_DIR / "data" / "images"
        self.mask_dir = BASE_DIR / "data" / "masks"

        self.image_paths = sorted(
            self.image_dir.glob("*.png")
        )

        if not self.image_paths:
            raise ValueError("No sketch images found!")

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        image_path = self.image_paths[index]
        mask_path = self.mask_dir / image_path.name

        # Input: black sketch on white background
        image = Image.open(image_path).convert("RGB")

        # Target: binary mask
        mask = Image.open(mask_path).convert("L")

        image = torch.from_numpy(
            np.array(image)
        ).permute(2, 0, 1).float() / 255.0

        mask = torch.from_numpy(
            (np.array(mask) > 0).astype(np.int64)
        )

        return image, mask
