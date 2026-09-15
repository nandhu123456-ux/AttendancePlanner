import { Link, useLocation } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";

export default function Nav() {
  const { pathname } = useLocation();
  const links = [["/dashboard", "Dashboard"], ["/subjects", "Subjects"], ["/prediction", "Prediction"], ["/settings", "Settings"]];
  return (
    <div className="nav-row">
      <nav className="nav-segmented" aria-label="Primary navigation">
        {links.map(([to, label]) => (
          <Link key={to} to={to} className={pathname === to ? "active" : ""} aria-current={pathname === to ? "page" : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      <ThemeToggle />
    </div>
  );
}
