import { useEffect, useState } from "react";
import { Link } from "react-router";
import { getHealth } from "./api";
import ScenePreview from "./ScenePreview";

type Connection =
  | { state: "loading" }
  | { state: "online"; service: string }
  | { state: "error"; message: string };

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
          <p className="eyebrow"><span /> A NEW PERSPECTIVE</p>
          <h1>Every great space<br />starts with<br /><em>a plan.</em></h1>
          <p className="description">
            A foundation for turning floor plans into a new dimension.
            Your workspace for exploring what comes next.
          </p>
          <Link className="primary-link" to="/workspace">Explore the workspace <span aria-hidden="true">&#8599;</span></Link>
          <p className="intro-note">Built for ideas. Ready for dimensions.</p>
        </div>
        <div className="preview">
          <div className="preview-heading">
            <span><span className="live-dot" /> LIVE 3D PREVIEW</span>
            <span className="preview-tag">CONCEPT 001</span>
          </div>
          <ScenePreview />
          <div className="preview-footer">
            <span>THE STARTING POINT</span>
            <span>Drag to orbit &middot; Scroll to zoom</span>
          </div>
        </div>
      </section>

      <section className="foundation" aria-label="Project foundation">
        <div className="section-label"><span>01 / THE FOUNDATION</span><h2>A connected starting point.</h2></div>
        <div className="feature-grid">
          <article className="feature">
            <span className="feature-number">01</span><h3>Your interface</h3>
            <p>React + TypeScript. A responsive home for your future floor plan tools.</p>
            <span className="feature-tag">FRONTEND READY</span>
          </article>
          <article className="feature">
            <span className="feature-number">02</span><h3>Your engine</h3>
            <p>Async FastAPI with typed Pydantic schemas, wall segmentation, and interactive docs.</p>
            <div className={`connection ${connection.state}`} role="status" aria-live="polite">
              <span className="live-dot" />
              {connection.state === "loading" && "CONNECTING TO API"}
              {connection.state === "online" && `${connection.service} connected`}
              {connection.state === "error" && "API UNAVAILABLE"}
            </div>
            {connection.state === "error" && (
              <div className="api-error">
                <p>{connection.message}</p>
                <button onClick={() => setAttempt((value) => value + 1)}>Retry connection</button>
              </div>
            )}
          </article>
          <article className="feature">
            <span className="feature-number">03</span><h3>Your next dimension</h3>
            <p>Three.js is wired in. Start with this interactive scene and make it your own.</p>
            <span className="feature-tag">3D FOUNDATION READY</span>
          </article>
        </div>
      </section>
    </>
  );
}
