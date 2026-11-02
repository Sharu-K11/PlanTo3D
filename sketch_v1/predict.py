
from pathlib import Path
import argparse

import numpy as np
import torch
from PIL import Image
import segmentation_models_pytorch as smp


BASE_DIR = Path(__file__).resolve().parent
CHECKPOINT = BASE_DIR / "checkpoints" / "sketch_model_v1.pth"

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

SIZE = 256

# Recreate the same architecture used for training
model = smp.Unet(
    encoder_name="resnet18",
    encoder_weights=None,
    in_channels=3,
    classes=2,
    activation=None
).to(DEVICE)

model.load_state_dict(
    torch.load(
        CHECKPOINT,
        map_location=DEVICE,
        weights_only=True
    )
)

model.eval()

mean = torch.tensor(
    [0.485, 0.456, 0.406],
    device=DEVICE
).view(1, 3, 1, 1)

std = torch.tensor(
    [0.229, 0.224, 0.225],
    device=DEVICE
).view(1, 3, 1, 1)


def predict(image_path):
    image = Image.open(image_path).convert("RGB")
    original_size = image.size

    # Resize to match training inputs
    image = image.resize(
        (SIZE, SIZE),
        Image.Resampling.BILINEAR
    )

    array = np.array(image)

    tensor = torch.from_numpy(
        array
    ).permute(2, 0, 1).float() / 255.0

    tensor = tensor.unsqueeze(0).to(DEVICE)
    tensor = (tensor - mean) / std

    with torch.inference_mode():
        logits = model(tensor)
        predicted = logits.argmax(dim=1)[0]

    mask_array = (
        predicted.cpu().numpy().astype(np.uint8) * 255
    )

    mask = Image.fromarray(mask_array)

    # Resize back to original dimensions
    mask = mask.resize(
        original_size,
        Image.Resampling.NEAREST
    )

    output_path = BASE_DIR / "predicted_sketch_mask.png"
    mask.save(output_path)

    print("Model:", CHECKPOINT)
    print("Input:", image_path)
    print("Device:", DEVICE)
    print("Saved:", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        required=True,
        help="Path to input sketch image"
    )
    args = parser.parse_args()

    predict(args.image)
