
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent

INPUT = BASE_DIR / "predicted_sketch_mask.png"
PRESERVED = BASE_DIR / "preserved_mask.png"
STRAIGHTENED = BASE_DIR / "straightened_mask.png"

if not INPUT.exists():
    raise FileNotFoundError(f"Mask not found: {INPUT}")

# Load the model's predicted mask
mask = cv2.imread(str(INPUT), cv2.IMREAD_GRAYSCALE)

# Convert to clean binary pixels
_, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

# Mode 1: Keep the prediction as-is
cv2.imwrite(str(PRESERVED), binary)

# Mode 2: Detect and straighten wall segments
lines = cv2.HoughLinesP(
    binary,
    rho=1,
    theta=np.pi / 180,
    threshold=20,
    minLineLength=15,
    maxLineGap=12
)

straight = np.zeros_like(binary)

count = 0

if lines is not None:
    lines = np.asarray(lines).reshape(-1, 4)

    for x1, y1, x2, y2 in lines:
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        if dx >= dy:
            # Force horizontal
            y = round((y1 + y2) / 2)
            p1 = (x1, y)
            p2 = (x2, y)
        else:
            # Force vertical
            x = round((x1 + x2) / 2)
            p1 = (x, y1)
            p2 = (x, y2)

        cv2.line(
            straight,
            p1,
            p2,
            color=255,
            thickness=5
        )
        count += 1

cv2.imwrite(str(STRAIGHTENED), straight)

# Side-by-side comparison
comparison = np.hstack([binary, straight])
cv2.imwrite(str(BASE_DIR / "wall_modes_comparison.png"), comparison)

print("Detected segments:", count)
print("Preserved:", PRESERVED)
print("Straightened:", STRAIGHTENED)
print("Comparison:", BASE_DIR / "wall_modes_comparison.png")
