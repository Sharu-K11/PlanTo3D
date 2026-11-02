import io
import json
import struct
import unittest

import support  # noqa: F401  # isort: skip  # must run before app imports

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.geometry_service import (
    PLAN_SIZE_M,
    WALL_HEIGHT_M,
    NoWallsDetectedError,
    _rectangles,
    mask_to_glb,
)

URL = "/api/v1/generate-3d"
COMPONENT_DTYPES = {5126: np.float32, 5125: np.uint32}
TYPE_SIZES = {"SCALAR": 1, "VEC3": 3}


def mask_png(walls: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.where(walls, 255, 0).astype(np.uint8), mode="L").save(buffer, "PNG")
    return buffer.getvalue()


def room_mask(width: int = 64, height: int = 40, wall: int = 3) -> np.ndarray:
    walls = np.zeros((height, width), dtype=bool)
    walls[:wall, :] = walls[-wall:, :] = True
    walls[:, :wall] = walls[:, -wall:] = True
    walls[:, width // 2 : width // 2 + wall] = True
    return walls


def parse_glb(data: bytes) -> tuple[dict, dict[str, dict[str, np.ndarray]]]:
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert (magic, version, length) == (0x46546C67, 2, len(data))
    json_length, json_type = struct.unpack_from("<II", data, 12)
    assert json_type == 0x4E4F534A
    gltf = json.loads(data[20 : 20 + json_length])
    bin_offset = 20 + json_length
    bin_length, bin_type = struct.unpack_from("<II", data, bin_offset)
    assert bin_type == 0x004E4942
    binary = data[bin_offset + 8 : bin_offset + 8 + bin_length]

    def read(index: int) -> np.ndarray:
        accessor = gltf["accessors"][index]
        view = gltf["bufferViews"][accessor["bufferView"]]
        array = np.frombuffer(
            binary,
            dtype=COMPONENT_DTYPES[accessor["componentType"]],
            count=accessor["count"] * TYPE_SIZES[accessor["type"]],
            offset=view["byteOffset"],
        )
        return array.reshape(accessor["count"], -1)

    meshes = {}
    for mesh in gltf["meshes"]:
        primitive = mesh["primitives"][0]
        meshes[mesh["name"]] = {
            "positions": read(primitive["attributes"]["POSITION"]),
            "normals": read(primitive["attributes"]["NORMAL"]),
            "indices": read(primitive["indices"]).reshape(-1),
        }
    return gltf, meshes


class GeometryTests(unittest.TestCase):
    def test_rectangles_merge_matching_rows(self) -> None:
        grid = np.zeros((4, 6), dtype=bool)
        grid[0:3, 1:3] = True  # one 2x3 block -> one rectangle
        grid[3, 4:6] = True
        self.assertEqual(sorted(_rectangles(grid)), [(1, 0, 3, 3), (4, 3, 6, 4)])

    def test_rectangles_cover_every_wall_cell_exactly_once(self) -> None:
        grid = np.random.default_rng(7).random((30, 40)) > 0.6
        covered = np.zeros(grid.shape, dtype=int)
        for x0, z0, x1, z1 in _rectangles(grid):
            covered[z0:z1, x0:x1] += 1
        np.testing.assert_array_equal(covered, grid.astype(int))

    def test_glb_is_valid_and_sized_in_metres(self) -> None:
        gltf, meshes = parse_glb(mask_to_glb(mask_png(room_mask())))
        self.assertEqual(gltf["asset"]["version"], "2.0")
        self.assertEqual(set(meshes), {"Floor", "Walls"})

        walls = meshes["Walls"]["positions"]
        self.assertAlmostEqual(float(walls[:, 1].min()), 0.0)
        self.assertAlmostEqual(float(walls[:, 1].max()), WALL_HEIGHT_M, places=5)
        self.assertAlmostEqual(float(np.ptp(walls[:, 0])), PLAN_SIZE_M, places=4)
        self.assertAlmostEqual(float(np.ptp(walls[:, 2])), PLAN_SIZE_M * 40 / 64, places=4)
        np.testing.assert_allclose(walls[:, [0, 2]].mean(axis=0), 0, atol=1.0)

        for accessor in gltf["accessors"]:
            if accessor["type"] == "VEC3":
                self.assertIn("min", accessor)
                self.assertIn("max", accessor)

    def test_triangles_face_outwards(self) -> None:
        _, meshes = parse_glb(mask_to_glb(mask_png(room_mask())))
        for name, mesh in meshes.items():
            with self.subTest(mesh=name):
                triangles = mesh["indices"].reshape(-1, 3)
                a, b, c = (mesh["positions"][triangles[:, i]] for i in range(3))
                face_normals = np.cross(b - a, c - a)
                agreement = np.einsum("ij,ij->i", face_normals, mesh["normals"][triangles[:, 0]])
                self.assertTrue(np.all(agreement > 0))
                self.assertLess(int(mesh["indices"].max()), len(mesh["positions"]))

    def test_large_masks_keep_thin_walls_and_are_downsampled(self) -> None:
        walls = np.zeros((1000, 2000), dtype=bool)
        walls[:, ::50] = True  # 40 one-pixel walls
        _, meshes = parse_glb(mask_to_glb(mask_png(walls)))
        boxes = len(meshes["Walls"]["positions"]) // 20
        self.assertEqual(boxes, 40)
        self.assertAlmostEqual(float(np.ptp(meshes["Floor"]["positions"][:, 0])), PLAN_SIZE_M, places=4)

    def test_empty_mask_raises(self) -> None:
        with self.assertRaises(NoWallsDetectedError):
            mask_to_glb(mask_png(np.zeros((10, 10), dtype=bool)))


class FakeSegmentationService:
    def __init__(self, walls: np.ndarray) -> None:
        self.walls = walls
        self.calls = 0

    def predict(self, image: Image.Image) -> bytes:
        self.calls += 1
        return mask_png(self.walls)


def plan_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 40), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class Generate3dEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app).__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def post(self, data: bytes, content_type: str = "image/png"):
        return self.client.post(URL, files={"file": ("plan.png", data, content_type)})

    def test_returns_glb(self) -> None:
        app.state.segmentation_service = FakeSegmentationService(room_mask())
        response = self.post(plan_png())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "model/gltf-binary")
        self.assertEqual(
            response.headers["content-disposition"], 'attachment; filename="building.glb"'
        )
        _, meshes = parse_glb(response.content)
        self.assertEqual(set(meshes), {"Floor", "Walls"})

    def test_no_walls_returns_422(self) -> None:
        app.state.segmentation_service = FakeSegmentationService(np.zeros((8, 8), dtype=bool))
        response = self.post(plan_png())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "No walls were detected in this plan")

    def test_validates_upload_before_inference(self) -> None:
        service = FakeSegmentationService(room_mask())
        app.state.segmentation_service = service
        self.assertEqual(self.post(plan_png(), content_type="image/jpeg").status_code, 400)
        self.assertEqual(self.post(b"not a png").status_code, 400)
        self.assertEqual(service.calls, 0)

    def test_returns_503_without_model(self) -> None:
        app.state.segmentation_service = None
        response = self.post(plan_png())
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
