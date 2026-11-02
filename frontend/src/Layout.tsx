import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { APP_VERSION, ISSUES_URL, REPO_URL } from "./site";

const TITLES: Record<string, string> = {
  "/": "Plan2World | Floor plan wall segmentation (Beta)",
  "/workspace": "Workspace | Plan2World",
};

export default function Layout() {
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = TITLES[pathname] ?? TITLES["/"];
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="app-shell">
      <header className="header">
        <Link className="brand" to="/" aria-label="Plan2World home">
          <span className="brand-mark" aria-hidden="true">P2</span>
          Plan2World<span className="brand-dot">.</span>
          <span className="beta-badge">BETA v{APP_VERSION}</span>
        </Link>
        <nav className="nav" aria-label="Main">
          <NavLink className="text-link" to="/workspace">Workspace</NavLink>
          <a className="text-link" href="/docs" target="_blank" rel="noreferrer">
            API docs <span aria-hidden="true">&#8599;</span>
          </a>
          <a className="text-link nav-github" href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub <span aria-hidden="true">&#8599;</span>
          </a>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="footer-grid">
          <div className="footer-brand">
            <Link className="brand" to="/" aria-label="Plan2World home">
              <span className="brand-mark" aria-hidden="true">P2</span>
              Plan2World<span className="brand-dot">.</span>
            </Link>
            <p>
              Wall segmentation for architectural floor plans, powered by the
              custom Plan2World model.
            </p>
            <span className="footer-status"><span className="live-dot" /> PUBLIC BETA &middot; v{APP_VERSION}</span>
          </div>
          <nav className="footer-col" aria-label="Product">
            <h2>Product</h2>
            <Link to="/workspace">Workspace</Link>
            <a href="/docs" target="_blank" rel="noreferrer">API documentation</a>
          </nav>
          <nav className="footer-col" aria-label="Project">
            <h2>Project</h2>
            <a href={REPO_URL} target="_blank" rel="noreferrer">Source on GitHub</a>
            <a href={ISSUES_URL} target="_blank" rel="noreferrer">Report an issue</a>
          </nav>
        </div>
        <div className="footer-bottom">
          <span>&copy; {new Date().getFullYear()} Plan2World</span>
          <span>Beta software: predictions may be inaccurate. Verify results before use.</span>
        </div>
      </footer>
    </div>
  );
}
