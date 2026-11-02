
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, random_split
import segmentation_models_pytorch as smp

from dataset import SketchDataset

# ==========================================
# 1. CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

BATCH_SIZE = 8
EPOCHS = 15
LEARNING_RATE = 0.0001
SEED = 42

torch.manual_seed(SEED)

# ==========================================
# 2. DATASET
# ==========================================

dataset = SketchDataset()

train_size = int(len(dataset) * 0.9)
val_size = len(dataset) - train_size

train_dataset, val_dataset = random_split(
    dataset,
    [train_size, val_size],
    generator=torch.Generator().manual_seed(SEED)
)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)

print("Training samples:", len(train_dataset))
print("Validation samples:", len(val_dataset))
print("Device:", DEVICE)

# ==========================================
# 3. PRETRAINED U-NET
# ==========================================

model = smp.Unet(
    encoder_name="resnet18",
    encoder_weights="imagenet",
    in_channels=3,
    classes=2,
    activation=None
).to(DEVICE)

# ImageNet normalization for pretrained encoder
MEAN = torch.tensor(
    [0.485, 0.456, 0.406],
    device=DEVICE
).view(1, 3, 1, 1)

STD = torch.tensor(
    [0.229, 0.224, 0.225],
    device=DEVICE
).view(1, 3, 1, 1)


def normalize(images):
    return (images - MEAN) / STD


# ==========================================
# 4. LOSS FUNCTION
# ==========================================

ce_loss = nn.CrossEntropyLoss()


def dice_loss(logits, targets):
    # Probability of being a wall
    probs = F.softmax(
        logits.float(), dim=1
    )[:, 1]

    targets = targets.float()

    intersection = (probs * targets).sum(dim=(1, 2))

    denominator = (
        probs.sum(dim=(1, 2))
        + targets.sum(dim=(1, 2))
    )

    dice = (
        2 * intersection + 1e-6
    ) / (
        denominator + 1e-6
    )

    return 1 - dice.mean()


# ==========================================
# 5. WALL IOU METRIC
# ==========================================

def wall_iou_counts(logits, targets):
    predicted = logits.argmax(dim=1) == 1
    actual = targets == 1

    intersection = (predicted & actual).sum().item()
    union = (predicted | actual).sum().item()

    return intersection, union


# ==========================================
# 6. OPTIMIZER + MIXED PRECISION
# ==========================================

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE
)

scaler = torch.amp.GradScaler(
    "cuda",
    enabled=DEVICE.type == "cuda"
)

best_iou = -1.0

# ==========================================
# 7. TRAINING LOOP
# ==========================================

for epoch in range(EPOCHS):
    model.train()
    train_loss = 0.0

    for images, masks in train_loader:
        images = normalize(images.to(DEVICE))
        masks = masks.to(DEVICE)

        optimizer.zero_grad(set_to_none=True)

        with torch.autocast(
            device_type=DEVICE.type,
            enabled=DEVICE.type == "cuda"
        ):
            outputs = model(images)

            loss = (
                ce_loss(outputs.float(), masks)
                + dice_loss(outputs, masks)
            )

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        train_loss += loss.item()

    # ======================================
    # VALIDATION
    # ======================================

    model.eval()

    val_loss = 0.0
    total_intersection = 0
    total_union = 0

    with torch.inference_mode():
        for images, masks in val_loader:
            images = normalize(images.to(DEVICE))
            masks = masks.to(DEVICE)

            with torch.autocast(
                device_type=DEVICE.type,
                enabled=DEVICE.type == "cuda"
            ):
                outputs = model(images)

            loss = (
                ce_loss(outputs.float(), masks)
                + dice_loss(outputs, masks)
            )

            val_loss += loss.item()

            intersection, union = wall_iou_counts(
                outputs, masks
            )

            total_intersection += intersection
            total_union += union

    avg_train = train_loss / len(train_loader)
    avg_val = val_loss / len(val_loader)

    val_iou = (
        total_intersection / total_union
        if total_union else 0.0
    )

    print(
        f"Epoch {epoch + 1}/{EPOCHS} | "
        f"Train Loss: {avg_train:.4f} | "
        f"Val Loss: {avg_val:.4f} | "
        f"Wall IoU: {val_iou:.4f}",
        flush=True
    )

    # Save best checkpoint
    if val_iou > best_iou:
        best_iou = val_iou

        torch.save(
            model.state_dict(),
            CHECKPOINT_DIR / "sketch_model_v1.pth"
        )

        print(
            f"  Best checkpoint saved: {best_iou:.4f}"
        )

print("\nTraining complete!")
print(f"Best validation Wall IoU: {best_iou:.4f}")
print("Saved:", CHECKPOINT_DIR / "sketch_model_v1.pth")
