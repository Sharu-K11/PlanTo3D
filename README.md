# Plan2World

**Beta — v0.0.4**

Async FastAPI + React/TypeScript foundation with an interactive Three.js home
page and a wall-segmentation endpoint. The API has no database for now; nothing
is stored.

The ML training scripts live in `model training/` and are not part of either
image. Datasets (any `data/` folder) and model weights (`*.pth`, `*.pt`,
`*.ckpt`, `*.safetensors`, `*.onnx`, `checkpoints/`) are gitignored, so a fresh
clone does not include them; copy them in separately.
The 3D scene on the home page is an illustrative placeholder.

## Run locally without Docker

Run the backend and frontend in **two terminals**. Nothing else is needed (no
database). Requires **Python 3.10+** and **Node.js 22.12+**.

> If the Docker stack is running, stop it first so ports are free:
> `docker compose stop`

### 1. One-time setup

From the project root:

```powershell
# Backend: separate venv so the ML training environment is untouched
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

# Optional: PyTorch + model libs, needed only for /api/v1/segment
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt

# Frontend
Set-Location frontend
npm.cmd ci
Set-Location ..
```

### 2. Start the backend (Terminal 1)

From the project root:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Or from inside `backend/` with the venv activated:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`--reload` restarts the server when Python files change. On startup the log
shows either `Segmentation model loaded successfully on cpu` or a warning
explaining why `/api/v1/segment` will return `503`.

### 3. Start the frontend (Terminal 2)

```powershell
Set-Location frontend
npm.cmd run dev
```

Vite hot-reloads React changes and forwards `/api/*`, `/docs`, and
`/openapi.json` to `http://127.0.0.1:8000`, so no CORS setup is needed.
(Override the target with `$env:BACKEND_URL` before `npm.cmd run dev`.)

### 4. Open

| What | URL |
|------|-----|
| App (React) | http://localhost:5173 |
| Workspace (upload a plan, detect walls) | http://localhost:5173/workspace |
| API docs (Scalar) | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/api/v1/health |

Test segmentation from the command line:

```powershell
curl.exe -F "file=@plan.png;type=image/png" http://127.0.0.1:8000/api/v1/segment -o wall_mask.png
```

Stop either server with `Ctrl+C`.

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `npm.ps1 cannot be loaded … running scripts is disabled` | Use `npm.cmd` instead of `npm` (as above). |
| `Activate.ps1 cannot be loaded` | Skip activation and use the full `backend\.venv\Scripts\python.exe -m uvicorn …` command. |
| `address already in use` on 8000 or 5173 | Stop the other process (e.g. `docker compose stop`), or pick another port with `--port 8001` and set `$env:BACKEND_URL="http://127.0.0.1:8001"` before starting Vite. |
| Page shows "API UNAVAILABLE" | The backend isn't running on port 8000; start Terminal 1. |
| `/api/v1/segment` returns `503` | Install `backend\requirements-ml.txt` and make sure `sketch_v1\checkpoints\sketch_model_v1.pth` exists; the Uvicorn log says which is missing. |
| Segmentation is slow | The venv has CPU-only PyTorch. For your GPU, install torch from `https://download.pytorch.org/whl/cu128` first. |

## Docker

Install Docker Desktop, start its Linux container engine, then from this root:

```powershell
docker compose up --build -d
```

- Home: http://localhost:8080
- API docs: http://localhost:8080/docs (proxied through the frontend)
- API health (direct): http://localhost:8000/api/v1/health

Host ports default to `8080` (frontend) and `8000` (backend) and bind to
`127.0.0.1` only. Override them in an optional root `.env`
(see [.env.example](.env.example)):

```dotenv
FRONTEND_PORT=8081
BACKEND_PORT=8001
```

```powershell
docker compose logs -f
docker compose down
```

Each service has its own Dockerfile and narrow build context. Datasets, weights,
and existing Python environments are not copied into either image. The frontend
is built with Vite and served by Nginx, which forwards `/api/*`, `/docs`, and
`/openapi.json` to FastAPI on the internal Compose network. Rebuild after source
changes.

## API

### Development mode

Set `DEV=true` in the root `.env` to enable Scalar at `/docs` and expose
`/openapi.json`. Set `DEV=false` to hide the schema and replace `/docs` with
an animated, lighthearted construction page. The API docs link still works,
but it cannot display API details in this mode. The animation respects reduced
motion preferences. If `DEV` is omitted, it defaults to `false`.

Restart Uvicorn after changing `.env` (Python auto-reload does not watch it).
For Docker, recreate the backend with `docker compose up -d backend`.
API endpoints continue working in either mode.

All routers are mounted under `/api/v1` in `backend/app/main.py`. Interactive
docs are served by [Scalar](https://github.com/scalar/scalar) at `/docs`
(Swagger UI and ReDoc are disabled); the Scalar page loads its JavaScript from
the jsDelivr CDN, so it needs internet access. The raw schema is at `/openapi.json`.

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | API status |
| `POST /api/v1/segment` | Upload one PNG (`file` field, ≤ 10 MB, ≤ 20 MP); returns the predicted wall mask as a PNG |
| `POST /api/v1/generate-3d` | Same upload; segments the plan and returns a 3D building as GLB (`model/gltf-binary`). `422` if no walls are detected |

## Workspace page

`/workspace` (linked from **Explore the workspace** on the home page and from
the header) is the UI for `/api/v1/segment` and `/api/v1/generate-3d`:

1. Drop or browse for a floor plan PNG. Type, size (10 MB), and resolution
   (20 MP) are checked in the browser before uploading.
2. **Detect walls** sends it to the API.
3. Review the result **side by side** or as a coloured **overlay** with an
   opacity slider, then **Download mask** (`<name>_walls.png`).
4. Open **3D model** to extrude the walls and explore them in Three.js (drag to
   orbit, right-drag to pan, scroll to zoom), then **Download GLB**
   (`<name>_3d.glb`, opens in Blender or any glTF viewer).

If the model isn't loaded (Docker/CI, or missing torch/weights) the page shows
"Segmentation model not loaded" with the fix; if the backend is down it shows
"API unavailable". Nothing is stored; images stay in the browser and the API
response.

### Segmentation (local only)

`/api/v1/segment` uses the U-Net in `backend/app/services/segmentation_service.py`
with the gitignored weights at `sketch_v1/checkpoints/sketch_model_v1.pth`
(override with `SEGMENTATION_MODEL_PATH`; disable with `SEGMENTATION_ENABLED=false`).
PyTorch is **not** installed in Docker or CI, so there the endpoint returns `503`.
To run it locally, install the ML extras into the backend venv:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
curl.exe -F "file=@plan.png;type=image/png" http://127.0.0.1:8000/api/v1/segment -o wall_mask.png
```

That installs the default CPU PyTorch wheel; for GPU, first install torch from
`https://download.pytorch.org/whl/cu128`. The model loads once at startup in a
worker thread; if weights or packages are missing, startup still succeeds and
the endpoint returns `503`.

### 3D generation

`/api/v1/generate-3d` runs the same segmentation, then
`backend/app/services/geometry_service.py` turns the mask into geometry with
NumPy only (no extra 3D libraries): wall pixels are merged into rectangles
(downsampled to at most 256 cells per side, keeping thin walls), extruded as
boxes, and placed on a floor. The plan's longest side is scaled to 20 m and walls
are 2.8 m high (`PLAN_SIZE_M`, `WALL_HEIGHT_M`); the GLB is Y-up, in metres, and
centred on the origin, with `Floor` and `Walls` meshes.

```powershell
curl.exe -F "file=@plan.png;type=image/png" http://127.0.0.1:8000/api/v1/generate-3d -o building.glb
```

## CORS

FastAPI allows `http://localhost:5173`, `http://127.0.0.1:5173`,
`http://localhost:8080`, and `http://127.0.0.1:8080` by default (Compose follows
`FRONTEND_PORT`).
Override `CORS_ORIGINS` with a comma-separated list of exact origins (no trailing
slash). For local development, set `$env:CORS_ORIGINS` before starting Uvicorn.
For Compose, set it in a root `.env` file or the shell before starting Compose.
Only GET and POST are currently allowed; expand allowed methods when adding
update or delete endpoints. CORS is not authentication.

## Structure

- `backend/app/main.py`: app, lifespan (model loading), CORS, `/api/v1` routers, Scalar `/docs`.
- `backend/app/config.py`: Pydantic settings from environment variables or the root `.env`.
- `backend/app/routers/`: `health.py`, `segmentation.py`.
- `backend/app/services/segmentation_service.py`: U-Net inference.
- `backend/app/services/geometry_service.py`: wall mask → extruded GLB.
- `backend/app/schemas.py`: Pydantic response models.
- `frontend/src/main.tsx`: React Router routes (`/` and `/workspace`).
- `frontend/src/Layout.tsx`: shared header/nav and footer.
- `frontend/src/Home.tsx`: home page and backend connectivity state.
- `frontend/src/Workspace.tsx`: upload, segmentation, 2D/3D result views, downloads.
- `frontend/src/api.ts`: typed API client (`getHealth`, `segmentImage`, `generateModel`).
- `frontend/src/ModelViewer.tsx`: Three.js GLB viewer (GLTFLoader, orbit
  controls, auto-framing, shadows, cleanup).
- `frontend/src/ScenePreview.tsx`: Three.js renderer, orbit controls, responsive
  sizing, and GPU-resource cleanup. Replace the sample geometry with future
  generated walls or loaded models here.
- `compose.yaml`: backend and frontend with health-gated startup.

## Continuous integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on pushes to `main`,
on pull requests, and manually (`workflow_dispatch`):

| Job | What it does |
|-----|--------------|
| **Backend tests** | Python 3.12; compiles and runs `unittest` (the real-model test is skipped because torch and weights are not installed). |
| **Frontend build** | Node 22, `npm ci`, then `npm run build` (TypeScript type-check + Vite build). |
| **Docker Compose smoke test** | Runs after both pass. Starts the stack and checks `/api/v1/health`, the home page, and `/docs` through Nginx. Prints logs on failure and always tears down. |

The workflow uses read-only permissions, cancels superseded runs on the same
branch, and needs no repository secrets.

## Validation

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
Push-Location frontend
npm.cmd run build
Pop-Location
docker compose config --quiet
```
