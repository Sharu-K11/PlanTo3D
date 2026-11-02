
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

# -----------------------------------
# 1. PATHS AND CONFIGURATION
# -----------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT = BASE_DIR / "predicted_sketch_mask.png"
OUTPUT = BASE_DIR / "straightened_mask_v2.png"
SKELETON = BASE_DIR / "skeleton.png"
COMPARISON = BASE_DIR / "comparison_v2.png"

WALL_THICKNESS = 5
AXIS_TOLERANCE = 8
MERGE_GAP = 15
CONNECT_GAP = 12

# -----------------------------------
# 2. LOAD MASK
# -----------------------------------

mask = cv2.imread(str(INPUT), cv2.IMREAD_GRAYSCALE)

if mask is None:
    raise FileNotFoundError(f"Cannot open {INPUT}")

_, binary = cv2.threshold(
    mask, 127, 255, cv2.THRESH_BINARY
)

# -----------------------------------
# 3. SKELETONIZATION
# -----------------------------------

skeleton = skeletonize(binary > 0)

skeleton_img = (
    skeleton.astype(np.uint8) * 255
)

cv2.imwrite(str(SKELETON), skeleton_img)

# -----------------------------------
# 4. DETECT LINE SEGMENTS
# -----------------------------------

lines = cv2.HoughLinesP(
    skeleton_img,
    rho=1,
    theta=np.pi / 180,
    threshold=12,
    minLineLength=12,
    maxLineGap=9
)

horizontal = []
vertical = []

if lines is not None:
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        if dx >= dy:
            horizontal.append((
                (int(y1) + int(y2)) / 2,
                int(min(x1, x2)),
                int(max(x1, x2))
            ))
        else:
            vertical.append((
                (int(x1) + int(x2)) / 2,
                int(min(y1, y2)),
                int(max(y1, y2))
            ))

# -----------------------------------
# 5. MERGE NEARBY PARALLEL SEGMENTS
# -----------------------------------

def merge_segments(segments, axis_tolerance, max_gap):
    if not segments:
        return []

    # Group segments by nearby axis position.
    groups = []

    for axis, start, end in sorted(segments):
        matching = None

        for group in groups:
            if abs(axis - group["axis"]) <= axis_tolerance:
                matching = group
                break

        if matching is None:
            groups.append({
                "axis": float(axis),
                "segments": [(start, end)],
                "positions": [axis]
            })
        else:
            matching["segments"].append((start, end))
            matching["positions"].append(axis)
            matching["axis"] = float(
                np.median(matching["positions"])
            )

    merged = []

    for group in groups:
        intervals = sorted(group["segments"])
        start, end = intervals[0]

        for next_start, next_end in intervals[1:]:
            if next_start <= end + max_gap:
                end = max(end, next_end)
            else:
                merged.append((group["axis"], start, end))
                start, end = next_start, next_end

        merged.append((group["axis"], start, end))

    return merged


horizontal = merge_segments(
    horizontal, AXIS_TOLERANCE, MERGE_GAP
)

vertical = merge_segments(
    vertical, AXIS_TOLERANCE, MERGE_GAP
)

# -----------------------------------
# 6. CONNECT NEARBY INTERSECTIONS
# -----------------------------------

# Expand endpoints only when a perpendicular segment
# is close enough to form a plausible junction.

def connect_intersections(h_lines, v_lines, tolerance):
    h = [list(s) for s in h_lines]
    v = [list(s) for s in v_lines]

    for hs in h:
        y, x1, x2 = hs

        for vs in v:
            x, y1, y2 = vs

            # Does the vertical line reach this horizontal?
            if not (y1 - tolerance <= y <= y2 + tolerance):
                continue

            # Does the horizontal line reach this vertical?
            if not (x1 - tolerance <= x <= x2 + tolerance):
                continue

            # Extend only nearby endpoints, not distant gaps.
            if x < x1 and x1 - x <= tolerance:
                hs[1] = x
            elif x > x2 and x - x2 <= tolerance:
                hs[2] = x

            if y < y1 and y1 - y <= tolerance:
                vs[1] = y
            elif y > y2 and y - y2 <= tolerance:
                vs[2] = y

    return h, v


horizontal, vertical = connect_intersections(
    horizontal, vertical, CONNECT_GAP
)

# -----------------------------------
# 7. REDRAW CLEAN WALLS
# -----------------------------------

straight = np.zeros_like(binary)

for y, x1, x2 in horizontal:
    cv2.line(
        straight,
        (round(x1), round(y)),
        (round(x2), round(y)),
        255,
        WALL_THICKNESS
    )

for x, y1, y2 in vertical:
    cv2.line(
        straight,
        (round(x), round(y1)),
        (round(x), round(y2)),
        255,
        WALL_THICKNESS
    )

# -----------------------------------
# 8. SAVE RESULTS
# -----------------------------------

cv2.imwrite(str(OUTPUT), straight)

comparison = np.hstack([
    binary,
    skeleton_img,
    straight
])

cv2.imwrite(str(COMPARISON), comparison)

print("Original size:", binary.shape)
print("Horizontal segments:", len(horizontal))
print("Vertical segments:", len(vertical))
print("Saved:", OUTPUT)
print("Saved:", SKELETON)
print("Saved:", COMPARISON)
