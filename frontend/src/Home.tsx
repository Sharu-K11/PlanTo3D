import { useEffect, useState } from "react";
import { Link } from "react-router";
import { getHealth } from "./api";
import ScenePreview from "./ScenePreview";
import { APP_VERSION, REPO_URL } from "./site";

type Connection =
  | { state: "loading" }
  | { state: "online"; service: string }
  | { state: "error"; message: string };

const SUPPORTED = ["Wall segmentation from PNG floor plans", "Downloadable binary wall mask", "Side-by-side and overlay review", "Experimental 3D wall extrusion (GLB)"];
const PLANNED = ["Doors and windows", "Room detection and labels", "Real-world scale and dimensions", "JPEG and PDF input"];

export default function Home() {
  const [connection, setConnection] = useState<Connection>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    let active = true;
    setConnection({ state: "loading" });

    getHealth(controller.signal)
      .then((health) => {
        if (active) setConnection({ state: "online", service: health.service });
      })
      .catch((error: unknown) => {
        if (active) {
          setConnection({
            state: "error",
            message: controller.signal.aborted
              ? "API request timed out. Check that the backend is running."
              : error instanceof Error ? error.message : "Could not reach the API.",
          });
        }
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  return (
    <>
      <section className="hero">
        <div className="intro">
          <p className="eyebrow"><span /> PUBLIC BETA &middot; WALL DETECTION</p>
          <h1>From floor plan<br />to wall map,<br /><em>in seconds.</em></h1>
          <p className="description">
            Plan2World is a custom segmentation model trained to find the walls in
            architectural floor plans. Upload a plan and get a pixel-level wall
            mask you can review, download, and preview in 3D.
          </p>
          <div className="hero-actions">
            <Link className="primary-link" to="/workspace">Open the workspace <span aria-hidden="true">&#8594;</span></Link>
            <a className="secondary-link" href={REPO_URL} target="_blank" rel="noreferrer">
              View on GitHub <span aria-hidden="true">&#8599;</span>
            </a>
          </div>
          <p className="intro-note">
            Beta v{APP_VERSION}: detects walls only. Doors, windows, and rooms are on the roadmap.
          </p>
        </div>
        <div className="preview">
          <div className="preview-heading">
            <span><span className="live-dot" /> 3D PREVIEW</span>
            <span className="preview-tag">SAMPLE SCENE</span>
          </div>
          <ScenePreview />
          <div className="preview-footer">
            <span>CONCEPT VISUALISATION</span>
            <span>Drag to orbit &middot; Scroll to zoom</span>
          </div>
        </div>
      </section>

      <section className="foundation" aria-labelledby="how-title">
        <div className="section-label"><span>01 / HOW IT WORKS</span><h2 id="how-title">One model, three steps.</h2></div>
        <div className="feature-grid">
          <article className="feature">
            <span className="feature-number">01</span><h3>Upload a plan</h3>
            <p>Drop a PNG floor plan up to 10 MB. Images are processed in memory and never stored.</p>
            <span className="feature-tag">PNG &middot; UP TO 20 MP</span>
          </article>
          <article className="feature">
            <span className="feature-number">02</span><h3>Detect the walls</h3>
            <p>The Plan2World model classifies every pixel as wall or background and returns a clean binary mask.</p>
            <div className={`connection ${connection.state}`} role="status" aria-live="polite">
              <span className="live-dot" />
              {connection.state === "loading" && "CHECKING MODEL API"}
              {connection.state === "online" && "MODEL API ONLINE"}
              {connection.state === "error" && "MODEL API UNAVAILABLE"}
            </div>
            {connection.state === "error" && (
              <div className="api-error">
                <p>{connection.message}</p>
                <button onClick={() => setAttempt((value) => value + 1)}>Retry connection</button>
              </div>
            )}
          </article>
          <article className="feature">
            <span className="feature-number">03</span><h3>Review &amp; export</h3>
            <p>Compare the mask with your plan, download it as PNG, or extrude the walls into a 3D GLB model.</p>
            <span className="feature-tag">3D PREVIEW IS EXPERIMENTAL</span>
          </article>
        </div>
      </section>

      <section className="scope" aria-labelledby="scope-title">
        <div className="section-label"><span>02 / BETA SCOPE</span><h2 id="scope-title">What this release can do.</h2></div>
        <div className="scope-grid">
          <div className="scope-card">
            <h3>Available now</h3>
            <ul>{SUPPORTED.map((item) => <li key={item} className="yes">{item}</li>)}</ul>
          </div>
          <div className="scope-card muted">
            <h3>On the roadmap</h3>
            <ul>{PLANNED.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        </div>
      </section>
    </>
  );
}
