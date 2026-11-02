"""Extrude a binary wall mask into a binary glTF (GLB) building model."""

import json
import struct
from io import BytesIO

import numpy as np
from PIL import Image

GRID_MAX_CELLS = 256  # cap on grid resolution; the model itself predicts at 256px
PLAN_SIZE_M = 20.0  # longest side of the plan, in metres
WALL_HEIGHT_M = 2.8

# glTF colours are linear RGB (sRGB ~ #f8f6f1 walls, #adbaa4 floor).
WALL_COLOR = [0.93, 0.92, 0.88, 1.0]
FLOOR_COLOR = [0.42, 0.49, 0.37, 1.0]

# Unit-cube faces as corner selectors (0 = min, 1 = max). No bottom face: walls sit on the floor.
_FACES = {
    (1, 0, 0): [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
    (-1, 0, 0): [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
    (0, 1, 0): [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
    (0, 0, 1): [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    (0, 0, -1): [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
}


def _oriented(normal: tuple[int, int, int], corners: list[tuple[int, int, int]]):
    """Order corners counter-clockwise when seen from outside, as glTF requires."""
    a, b, c = (np.array(corner, dtype=float) for corner in corners[:3])
    return corners if np.dot(np.cross(b - a, c - a), normal) > 0 else corners[::-1]


_BOX_CORNERS = np.array(
    [_oriented(n, c) for n, c in _FACES.items()], dtype=np.float32
).reshape(-1, 3)
_BOX_NORMALS = np.repeat(np.array(list(_FACES), dtype=np.float32), 4, axis=0)
_BOX_INDICES = np.concatenate(
    [np.array([0, 1, 2, 0, 2, 3]) + 4 * face for face in range(len(_FACES))]
).astype(np.uint32)


class NoWallsDetectedError(ValueError):
    pass


def _wall_grid(mask_png: bytes) -> tuple[np.ndarray, int, tuple[int, int]]:
    """Return (wall cells, pixels per cell, original (rows, cols)). Downsampling keeps
    a cell if any of its pixels is a wall, so thin walls never vanish."""
    with Image.open(BytesIO(mask_png)) as mask:
        walls = np.asarray(mask.convert("L")) > 127
    rows, cols = walls.shape
    factor = max(1, -(-max(rows, cols) // GRID_MAX_CELLS))
    if factor > 1:
        walls = np.pad(walls, ((0, -rows % factor), (0, -cols % factor)))
        walls = walls.reshape(walls.shape[0] // factor, factor, -1, factor).any(axis=(1, 3))
    return walls, factor, (rows, cols)


def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate(([False], row, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def _rectangles(grid: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Merge wall cells into (x0, z0, x1, z1) rectangles; identical runs on
    consecutive rows grow downwards, which keeps the triangle count low."""
    rects: list[tuple[int, int, int, int]] = []
    open_runs: dict[tuple[int, int], int] = {}
    for z, row in enumerate(grid):
        current = set(_runs(row))
        for run, z0 in list(open_runs.items()):
            if run not in current:
                rects.append((run[0], z0, run[1], z))
                del open_runs[run]
        for run in current:
            open_runs.setdefault(run, z)
    rects.extend((x0, z0, x1, len(grid)) for (x0, x1), z0 in open_runs.items())
    return rects


def _wall_mesh(rects: list[tuple[int, int, int, int]], cell: float, offset: np.ndarray):
    boxes = np.array(rects, dtype=np.float32)
    lo = np.stack([boxes[:, 0], np.zeros(len(boxes)), boxes[:, 1]], axis=1) * [cell, 1, cell]
    hi = np.stack([boxes[:, 2], np.full(len(boxes), WALL_HEIGHT_M), boxes[:, 3]], axis=1)
    hi *= [cell, 1, cell]
    lo, hi = lo - offset, hi - offset
    positions = lo[:, None, :] + _BOX_CORNERS[None] * (hi - lo)[:, None, :]
    normals = np.broadcast_to(_BOX_NORMALS, positions.shape)
    indices = _BOX_INDICES[None] + (np.arange(len(boxes), dtype=np.uint32) * len(_BOX_CORNERS))[:, None]
    return positions.reshape(-1, 3), normals.reshape(-1, 3), indices.reshape(-1)


def _floor_mesh(width: float, depth: float):
    x, z = width / 2, depth / 2
    positions = np.array([[-x, 0, -z], [-x, 0, z], [x, 0, z], [x, 0, -z]], dtype=np.float32)
    normals = np.tile(np.array([0, 1, 0], dtype=np.float32), (4, 1))
    return positions, normals, np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)


def _to_glb(meshes: list[tuple[str, list[float], tuple[np.ndarray, np.ndarray, np.ndarray]]]) -> bytes:
    gltf: dict = {
        "asset": {"version": "2.0", "generator": "Plan2World"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(meshes)))}],
        "nodes": [],
        "meshes": [],
        "materials": [],
        "accessors": [],
        "bufferViews": [],
    }
    binary = bytearray()

    def add_accessor(data: np.ndarray, kind: str, component: int, target: int) -> int:
        offset = len(binary)
        binary.extend(np.ascontiguousarray(data).tobytes())
        binary.extend(b"\x00" * (-len(binary) % 4))
        gltf["bufferViews"].append(
            {"buffer": 0, "byteOffset": offset, "byteLength": data.nbytes, "target": target}
        )
        accessor = {
            "bufferView": len(gltf["bufferViews"]) - 1,
            "componentType": component,
            "count": len(data),
            "type": kind,
        }
        if kind == "VEC3":
            accessor["min"] = data.min(axis=0).tolist()
            accessor["max"] = data.max(axis=0).tolist()
        gltf["accessors"].append(accessor)
        return len(gltf["accessors"]) - 1

    for index, (name, color, (positions, normals, indices)) in enumerate(meshes):
        gltf["materials"].append(
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": color,
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.85,
                },
            }
        )
        primitive = {
            "attributes": {
                "POSITION": add_accessor(positions.astype(np.float32), "VEC3", 5126, 34962),
                "NORMAL": add_accessor(normals.astype(np.float32), "VEC3", 5126, 34962),
            },
            "indices": add_accessor(indices.astype(np.uint32), "SCALAR", 5125, 34963),
            "material": index,
        }
        gltf["meshes"].append({"name": name, "primitives": [primitive]})
        gltf["nodes"].append({"name": name, "mesh": index})

    gltf["buffers"] = [{"byteLength": len(binary)}]
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode()
    json_chunk += b" " * (-len(json_chunk) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(binary)
    return b"".join(
        [
            struct.pack("<III", 0x46546C67, 2, total),  # "glTF", version 2
            struct.pack("<II", len(json_chunk), 0x4E4F534A),  # "JSON"
            json_chunk,
            struct.pack("<II", len(binary), 0x004E4942),  # "BIN\0"
            bytes(binary),
        ]
    )


def mask_to_glb(mask_png: bytes) -> bytes:
    """Build a GLB with a floor and extruded walls (Y up, metres, centred on the origin)."""
    grid, factor, (rows, cols) = _wall_grid(mask_png)
    rects = _rectangles(grid)
    if not rects:
        raise NoWallsDetectedError("No walls were detected in this plan")

    # Rectangles in original pixels, clipped to the image (padding may overhang).
    rects = [
        (x0 * factor, z0 * factor, min(x1 * factor, cols), min(z1 * factor, rows))
        for x0, z0, x1, z1 in rects
    ]
    cell = PLAN_SIZE_M / max(rows, cols)
    width, depth = cols * cell, rows * cell
    offset = np.array([width / 2, 0, depth / 2], dtype=np.float32)
    return _to_glb(
        [
            ("Floor", FLOOR_COLOR, _floor_mesh(width, depth)),
            ("Walls", WALL_COLOR, _wall_mesh(rects, cell, offset)),
        ]
    )
