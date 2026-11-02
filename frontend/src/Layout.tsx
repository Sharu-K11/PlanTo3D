import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";

const TITLES: Record<string, string> = {
  "/": "Plan2World | Your next dimension",
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
          <span className="beta-badge">BETA v0.0.4</span>
        </Link>
        <nav className="nav" aria-label="Main">
          <NavLink className="text-link" to="/workspace">Workspace</NavLink>
          <a className="text-link" href="/docs" target="_blank" rel="noreferrer">
            API docs <span aria-hidden="true">&#8599;</span>
          </a>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="footer"><span>Plan2World</span><span>FROM A SIMPLE PLAN TO SOMETHING MORE.</span><span>BETA v0.0.4</span></footer>
    </div>
  );
}
