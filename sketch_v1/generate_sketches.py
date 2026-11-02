
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import random

# ----------------------------------
# CONFIGURATION
# ----------------------------------

BASE_DIR = Path(__file__).resolve().parent

IMAGE_DIR = BASE_DIR / "data" / "images"
MASK_DIR = BASE_DIR / "data" / "masks"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
MASK_DIR.mkdir(parents=True, exist_ok=True)

COUNT = 1000
SIZE = 256
SEED = 42

random.seed(SEED)


def make_layout():
    """Generate a clean floor-plan layout."""

    margin = random.randint(25, 40)

    left = margin
    top = margin
    right = SIZE - margin
    bottom = SIZE - margin

    walls = [
        ((left, top), (right, top)),
        ((right, top), (right, bottom)),
        ((right, bottom), (left, bottom)),
        ((left, bottom), (left, top)),
    ]

    # Random vertical partition
    if random.random() < 0.9:
        x = random.randint(left + 35, right - 35)
        walls.append(((x, top), (x, bottom)))

    # Random horizontal partition
    if random.random() < 0.9:
        y = random.randint(top + 35, bottom - 35)
        walls.append(((left, y), (right, y)))

    # Additional partial walls
    for _ in range(random.randint(0, 3)):
        if random.random() < 0.5:
            y = random.randint(top + 20, bottom - 20)
            x1 = random.randint(left, right - 30)
            x2 = random.randint(x1 + 20, right)
            walls.append(((x1, y), (x2, y)))
        else:
            x = random.randint(left + 20, right - 20)
            y1 = random.randint(top, bottom - 30)
            y2 = random.randint(y1 + 20, bottom)
            walls.append(((x, y1), (x, y2)))

    return walls


def draw_mask(walls):
    """Create clean wall segmentation mask."""

    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)

    for start, end in walls:
        draw.line(
            [start, end],
            fill=255,
            width=5
        )

    return mask


def draw_sketch(walls):
    """Create imperfect hand-drawn version."""

    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)

    for start, end in walls:
        x1, y1 = start
        x2, y2 = end

        # Slightly distort the endpoints
        jitter = 3

        p1 = (
            x1 + random.randint(-jitter, jitter),
            y1 + random.randint(-jitter, jitter)
        )

        p2 = (
            x2 + random.randint(-jitter, jitter),
            y2 + random.randint(-jitter, jitter)
        )

        # Slightly irregular stroke
        width = random.randint(2, 4)

        draw.line(
            [p1, p2],
            fill=(random.randint(0, 45),) * 3,
            width=width
        )

    # Mild blur simulates imperfect image capture
    if random.random() < 0.3:
        image = image.filter(
            ImageFilter.GaussianBlur(radius=0.4)
        )

    return image


# ----------------------------------
# GENERATE DATASET
# ----------------------------------

for index in range(COUNT):
    walls = make_layout()

    image = draw_sketch(walls)
    mask = draw_mask(walls)

    filename = f"sketch_{index:05d}.png"

    image.save(IMAGE_DIR / filename)
    mask.save(MASK_DIR / filename)

    if (index + 1) % 100 == 0:
        print(f"Generated {index + 1}/{COUNT}")

print("\nDataset generation complete!")
print("Images:", IMAGE_DIR)
print("Masks:", MASK_DIR)
