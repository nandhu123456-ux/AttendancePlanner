import { Link, useLocation } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";

export default function Nav() {
  const { pathname } = useLocation();
  const links = [["/dashboard", "Dashboard"], ["/subjects", "Subjects"], ["/history", "Attendance History"], ["/prediction", "Prediction"], ["/settings", "Settings"]];
  return <nav className="nav-actions">{links.map(([to, label]) => <Link key={to} className={pathname === to ? "active" : ""} to={to}>{label}</Link>)}<ThemeToggle /></nav>;
}
