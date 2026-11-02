import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { ApiError, MAX_UPLOAD_BYTES, generateModel, segmentImage } from "./api";
import ModelViewer from "./ModelViewer";

const MAX_PIXELS = 20_000_000;
const REQUEST_TIMEOUT_MS = 120_000;

type Source = { file: File; url: string; width?: number; height?: number };

type Run =
  | { state: "idle" }
  | { state: "running" }
  | { state: "done"; maskUrl: string; seconds: number }
  | { state: "error"; title: string; message: string };

type Model =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "done"; data: ArrayBuffer; url: string; seconds: number }
  | { state: "error"; title: string; message: string };

type View = "side" | "overlay" | "3d";

const SAMPLES = [
  { file: "sample1.png", label: "Central hall" },
  { file: "sample2.png", label: "Courtyard" },
  { file: "sample3.png", label: "Open core" },
  { file: "sample4.png", label: "Corridor" },
] as const;

const VIEW_LABELS: Record<View, string> = { side: "Side by side", overlay: "Overlay", "3d": "3D model" };

function formatSeconds(seconds: number): string {
  return seconds < 1 ? `${Math.max(1, Math.round(seconds * 1000))} ms` : `${seconds.toFixed(1)}s`;
}

function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function validate(file: File): string | null {
  if (file.type !== "image/png") return "Only PNG images are supported.";
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) return `File is ${formatBytes(file.size)}; the limit is 10 MB.`;
  return null;
}

const UNAVAILABLE = { title: "API unavailable", message: "Could not reach the backend. Check that Uvicorn is running." };

function describeError(error: unknown, timedOut: boolean): { title: string; message: string } {
  if (timedOut) return { title: "Request timed out", message: "The server took too long to respond. Try a smaller image." };
  if (!(error instanceof ApiError)) return UNAVAILABLE;
  if (error.status === 503) {
    return {
      title: "Segmentation model not loaded",
      message: `${error.message}. Run the backend locally with requirements-ml.txt installed and the model weights in sketch_v1/checkpoints.`,
    };
  }
  // Proxies (Vite/Nginx) answer with a non-JSON 5xx when the backend is down.
  if (error.status >= 500 && error.message.startsWith("Request failed with HTTP")) return UNAVAILABLE;
  return { title: "Could not process this image", message: error.message };
}

export default function Workspace() {
  const [source, setSource] = useState<Source | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);
  const [run, setRun] = useState<Run>({ state: "idle" });
  const [model, setModel] = useState<Model>({ state: "idle" });
  const [view, setView] = useState<View>("side");
  const [opacity, setOpacity] = useState(0.65);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const modelRequestRef = useRef<AbortController | null>(null);

  // Revoke object URLs when they are replaced or the page unmounts.
  const sourceUrl = source?.url;
  const maskUrl = run.state === "done" ? run.maskUrl : undefined;
  const modelUrl = model.state === "done" ? model.url : undefined;
  useEffect(() => () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl); }, [sourceUrl]);
  useEffect(() => () => { if (maskUrl) URL.revokeObjectURL(maskUrl); }, [maskUrl]);
  useEffect(() => () => { if (modelUrl) URL.revokeObjectURL(modelUrl); }, [modelUrl]);
  useEffect(() => () => { requestRef.current?.abort(); modelRequestRef.current?.abort(); }, []);

  const resetModel = useCallback(() => {
    modelRequestRef.current?.abort();
    modelRequestRef.current = null;
    setModel({ state: "idle" });
  }, []);

  const selectFile = useCallback((file: File | undefined) => {
    if (!file) return;
    requestRef.current?.abort();
    resetModel();
    setRun({ state: "idle" });
    setView((current) => (current === "3d" ? "side" : current));
    const problem = validate(file);
    if (problem) {
      setRejection(`${file.name}: ${problem}`);
      return;
    }
    setRejection(null);
    setSource({ file, url: URL.createObjectURL(file) });
  }, [resetModel]);

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    selectFile(event.target.files?.[0]);
    event.target.value = "";
  };

  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const loadSample = async (name: string) => {
    setLoadingSample(name);
    try {
      const response = await fetch(`/samples/${name}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      selectFile(new File([blob], name, { type: "image/png" }));
    } catch {
      setRejection("Could not load the sample plan. Please try again.");
    } finally {
      setLoadingSample(null);
    }
  };

  // Ctrl+V / Cmd+V anywhere on the page: paste a copied drawing (e.g. from Paint).
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const item = [...(event.clipboardData?.items ?? [])].find((entry) => entry.kind === "file" && entry.type.startsWith("image/"));
      const blob = item?.getAsFile();
      if (!blob) return;
      event.preventDefault();
      const stamp = new Date().toISOString().slice(11, 19).replaceAll(":", "");
      selectFile(new File([blob], `pasted-plan-${stamp}.png`, { type: blob.type }));
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [selectFile]);

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files[0]);
  };

  const onSourceLoaded = (width: number, height: number) => {
    setSource((current) => (current ? { ...current, width, height } : current));
    if (width * height > MAX_PIXELS) {
      setRejection(`Image is ${width} × ${height} (${(width * height / 1e6).toFixed(1)} MP); the limit is 20 MP.`);
    }
  };

  const tooLarge = Boolean(source?.width && source.height && source.width * source.height > MAX_PIXELS);

  const detectWalls = async () => {
    if (!source || tooLarge) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, REQUEST_TIMEOUT_MS);
    const started = performance.now();
    resetModel();
    setView((current) => (current === "3d" ? "side" : current));
    setRun({ state: "running" });
    try {
      const mask = await segmentImage(source.file, controller.signal);
      if (requestRef.current !== controller) return;
      setRun({ state: "done", maskUrl: URL.createObjectURL(mask), seconds: (performance.now() - started) / 1000 });
    } catch (error) {
      if (requestRef.current !== controller || (controller.signal.aborted && !timedOut)) return;
      setRun({ state: "error", ...describeError(error, timedOut) });
    } finally {
      window.clearTimeout(timeout);
      if (requestRef.current === controller) requestRef.current = null;
    }
  };

  const buildModel = async () => {
    if (!source || tooLarge) return;
    modelRequestRef.current?.abort();
    const controller = new AbortController();
    modelRequestRef.current = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, REQUEST_TIMEOUT_MS);
    const started = performance.now();
    setModel({ state: "loading" });
    try {
      const data = await generateModel(source.file, controller.signal);
      if (modelRequestRef.current !== controller) return;
      const url = URL.createObjectURL(new Blob([data], { type: "model/gltf-binary" }));
      setModel({ state: "done", data, url, seconds: (performance.now() - started) / 1000 });
    } catch (error) {
      if (modelRequestRef.current !== controller || (controller.signal.aborted && !timedOut)) return;
      setModel({ state: "error", ...describeError(error, timedOut) });
    } finally {
      window.clearTimeout(timeout);
      if (modelRequestRef.current === controller) modelRequestRef.current = null;
    }
  };

  const chooseView = (mode: View) => {
    setView(mode);
    if (mode === "3d" && model.state === "idle") void buildModel();
  };

  const baseName = source?.file.name.replace(/\.png$/i, "") ?? "plan";
  const running = run.state === "running";

  return (
    <section className="workspace" aria-labelledby="workspace-title">
      <div className="workspace-head">
        <div>
          <p className="eyebrow"><span /> 02 / THE WORKSPACE</p>
          <h1 id="workspace-title" className="workspace-title">Find the <em>walls.</em></h1>
          <p className="description">
            Upload a floor plan PNG. The Plan2World model detects the walls and
            returns a mask you can download, overlay on the original, or preview
            as an experimental 3D model.
          </p>
          <p className="beta-note">
            <strong>Beta</strong> Walls only for now. Doors, windows, and rooms are not detected yet.
          </p>
        </div>
        <ol className="steps" aria-label="How it works">
          <li className={source ? "done" : "current"}><span>01</span>Upload a plan</li>
          <li className={run.state === "done" ? "done" : source ? "current" : ""}><span>02</span>Detect walls</li>
          <li className={run.state === "done" ? "current" : ""}><span>03</span>Review in 2D &amp; 3D</li>
        </ol>
      </div>

      {!source && (
        <label
          htmlFor="plan-file"
          className={`dropzone${dragging ? " dragging" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <span className="dropzone-icon" aria-hidden="true">&#8593;</span>
          <strong>Drop a floor plan here</strong>
          <span>or <u>browse your files</u> &middot; or paste with <kbd>Ctrl</kbd>+<kbd>V</kbd></span>
          <small>PNG only &middot; up to 10 MB &middot; up to 20 megapixels</small>
        </label>
      )}
      <input
        ref={inputRef}
        id="plan-file"
        type="file"
        accept="image/png"
        onChange={onInputChange}
        className="visually-hidden"
        aria-label="Choose a floor plan PNG"
      />

      {rejection && <p className="notice error" role="alert">{rejection}</p>}

      {!source && (
        <section className="samples" aria-labelledby="samples-title">
          <div className="samples-head">
            <h2 id="samples-title">No plan handy? Try a sample.</h2>
            <p>Hand-drawn style sketches like the ones the Plan2World model was trained on.</p>
          </div>
          <div className="samples-grid">
            {SAMPLES.map((sample) => (
              <button
                key={sample.file}
                type="button"
                className="sample-card"
                onClick={() => loadSample(sample.file)}
                disabled={loadingSample !== null}
                aria-busy={loadingSample === sample.file}
              >
                <img src={`/samples/thumbs/${sample.file}`} alt="" width={320} height={320} loading="lazy" />
                <span>{loadingSample === sample.file ? "Loading…" : sample.label}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {!source && (
        <section className="draw-guide" aria-labelledby="draw-title">
          <div className="draw-intro">
            <p className="eyebrow"><span /> TRY IT YOURSELF</p>
            <h2 id="draw-title">Sketch a plan in Paint.</h2>
            <p>
              No floor plan file? Draw one in under a minute with Microsoft Paint
              or any drawing app. The model is trained on simple sketches, so a
              rough drawing works best.
            </p>
          </div>
          <ol className="draw-steps">
            <li>
              <strong>Open Paint</strong>
              <span>Press <kbd>Win</kbd>, type <em>Paint</em>, and start a new white canvas.</span>
            </li>
            <li>
              <strong>Draw the walls</strong>
              <span>Use the line tool with a thick, dark brush (5px or more). Draw an outer box, then a few lines to split it into rooms.</span>
            </li>
            <li>
              <strong>Copy it</strong>
              <span>Press <kbd>Ctrl</kbd>+<kbd>A</kbd> then <kbd>Ctrl</kbd>+<kbd>C</kbd>, or save it as a PNG.</span>
            </li>
            <li>
              <strong>Paste it here</strong>
              <span>Come back and press <kbd>Ctrl</kbd>+<kbd>V</kbd>, or drop the PNG above, then click <em>Detect walls</em>.</span>
            </li>
          </ol>
          <p className="draw-tip">
            Tips: black lines on white, keep the plan roughly square, and skip text,
            furniture, and dimensions. They are not supported in this beta.
          </p>
        </section>
      )}

      {source && (
        <div className="workbench">
          <div className="toolbar">
            <div className="file-meta">
              <strong title={source.file.name}>{source.file.name}</strong>
              <span>
                {formatBytes(source.file.size)}
                {source.width && source.height ? ` · ${source.width} × ${source.height}px` : ""}
                {run.state === "done" ? ` · processed in ${formatSeconds(run.seconds)}` : ""}
              </span>
            </div>
            <div className="toolbar-actions">
              <button type="button" className="ghost-button" onClick={() => inputRef.current?.click()} disabled={running}>
                Choose another
              </button>
              {run.state === "done" ? (
                <a className="primary-button" href={run.maskUrl} download={`${baseName}_walls.png`}>
                  Download mask <span aria-hidden="true">&#8595;</span>
                </a>
              ) : (
                <button type="button" className="primary-button" onClick={detectWalls} disabled={running || tooLarge}>
                  {running ? "Detecting walls…" : "Detect walls"}
                  {!running && <span aria-hidden="true">&#8594;</span>}
                </button>
              )}
            </div>
          </div>

          {run.state === "error" && (
            <div className="notice error" role="alert">
              <strong>{run.title}</strong>
              <p>{run.message}</p>
              <button type="button" className="ghost-button" onClick={detectWalls}>Try again</button>
            </div>
          )}

          {run.state === "done" && (
            <div className="view-controls">
              <div className="segmented" role="radiogroup" aria-label="Result view">
                {(["side", "overlay", "3d"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    role="radio"
                    aria-checked={view === mode}
                    className={view === mode ? "active" : ""}
                    onClick={() => chooseView(mode)}
                  >
                    {VIEW_LABELS[mode]}
                  </button>
                ))}
              </div>
              {view === "overlay" && (
                <label className="opacity-control">
                  Wall opacity
                  <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
                </label>
              )}
              {view === "3d" && model.state === "done" && (
                <a className="ghost-button" href={model.url} download={`${baseName}_3d.glb`}>
                  Download GLB <span aria-hidden="true">&#8595;</span>
                </a>
              )}
            </div>
          )}

          {run.state === "done" && view === "3d" ? (
            <figure className="panel model-panel">
              <figcaption>
                3D model{model.state === "done" ? ` · built in ${formatSeconds(model.seconds)}` : ""}
              </figcaption>
              <div className="model-stage" aria-busy={model.state === "loading"}>
                {model.state === "done" && <ModelViewer data={model.data} label={`3D model of ${source.file.name}`} />}
                {model.state === "loading" && (
                  <div className="model-status" role="status">
                    <span className="model-spinner" aria-hidden="true" />
                    Raising the walls…
                  </div>
                )}
                {model.state === "error" && (
                  <div className="model-status notice error" role="alert">
                    <strong>{model.title}</strong>
                    <p>{model.message}</p>
                    <button type="button" className="ghost-button" onClick={buildModel}>Try again</button>
                  </div>
                )}
              </div>
            </figure>
          ) : (
          <div className={`canvas-grid${run.state === "done" && view === "side" ? " two" : ""}`} aria-busy={running}>
            <figure className="panel">
              <figcaption>{run.state === "done" && view === "overlay" ? "Plan + detected walls" : "Original plan"}</figcaption>
              <div className="image-stage">
                <div className="image-frame">
                  <img
                    src={source.url}
                    alt={`Uploaded floor plan ${source.file.name}`}
                    onLoad={(e) => onSourceLoaded(e.currentTarget.naturalWidth, e.currentTarget.naturalHeight)}
                  />
                  {run.state === "done" && view === "overlay" && (
                    <div
                      className="mask-overlay"
                      style={{ opacity, maskImage: `url(${run.maskUrl})`, WebkitMaskImage: `url(${run.maskUrl})` }}
                      aria-hidden="true"
                    />
                  )}
                </div>
                {running && (
                  <div className="scanning" role="status">
                    <span className="scan-line" aria-hidden="true" />
                    <span className="scan-label">Detecting walls…</span>
                  </div>
                )}
              </div>
            </figure>
            {run.state === "done" && view === "side" && (
              <figure className="panel">
                <figcaption>Detected walls</figcaption>
                <div className="image-stage mask-stage">
                  <div className="image-frame">
                    <img src={run.maskUrl} alt="Predicted wall mask: walls in white on black" />
                  </div>
                </div>
              </figure>
            )}
          </div>
          )}
        </div>
      )}
    </section>
  );
}
