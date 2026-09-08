import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import { Link } from "react-router-dom";
import { getPlanner, sync } from "../api/api";
import "./Dashboard.css";

const Metric = ({ label, value, hint, status }) => (
  <article className={`metric ${status ? `metric-${status}` : ""}`}>
    <p>{label}</p>
    <strong>{value}</strong>
    {hint && <span>{hint}</span>}
  </article>
);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [success] = useState(() => {
    const message = sessionStorage.getItem("predictionUpdated");
    sessionStorage.removeItem("predictionUpdated");
    return message;
  });
  const navigate = useNavigate();

  useEffect(() => {
    const id = localStorage.getItem("student_id");
    if (!id) return navigate("/login");
    getPlanner(id).then(({ data }) => setData(data)).catch((err) => setError(err.response?.data?.detail || "Unable to load your attendance plan."));
  }, [navigate]);

  const runSync = async () => {
    const id = localStorage.getItem("student_id");
    setSyncing(true);
    setSyncMessage("");
    try {
      const { data: syncData } = await sync(id);
      setSyncMessage(
        syncData.needs_target_date
          ? "Attendance updated. Set a target date in Settings to recalculate your plan."
          : "Attendance updated"
      );
      // Re-load the plan so Current/Remaining/Projected reflect the latest synced attendance.
      const plan = await getPlanner(id);
      setData(plan.data);
    } catch (err) {
      setSyncMessage(err.response?.data?.detail || "Sync failed. Please log in again and retry.");
    } finally {
      setSyncing(false);
    }
  };

  const logout = () => { localStorage.clear(); navigate("/login"); };

  if (error) return <main className="state"><h1>Attendance Planner</h1><p>{error}</p><button onClick={logout}>Return to login</button></main>;
  if (!data) return <main className="state"><div className="spinner" /><p>Building your attendance plan…</p></main>;

  const { overall, warnings } = data;
  const calInfo = data.calendar_info || {};

  const getAttendanceStatus = (pct, target) => {
    if (pct >= target) return "good";
    if (pct >= target - 10) return "warning";
    return "danger";
  };

  const formatDate = (iso) => {
    const parsed = new Date(iso);
    return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <div className="brand-header-inline">
            <svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 4L4 14v12l16 10 16-10V14L20 4z" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M20 4v32M4 14l16 10 16-10M4 26l16-10 16 10" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <circle cx="20" cy="18" r="4" fill="currentColor"/>
            </svg>
            <p className="eyebrow">TRACK_75</p>
          </div>
          <h1>Dashboard</h1>
          {calInfo.sessional && (
            <p className="sessional-badge">
              {calInfo.academic_year && (
                <span className="academic-year-badge">{calInfo.academic_year} ({calInfo.semester_type || "ODD"})</span>
              )}
              <span>Targeting {calInfo.sessional.replace("_", "-").toUpperCase()}</span>
              {calInfo.sessional_end ? ` · ends ${calInfo.sessional_end}` : ""}
            </p>
          )}
        </div>
        <div className="nav-actions">
          <button type="button" className="change-date-control sync-control" onClick={runSync} disabled={syncing} title="Fetch the latest attendance from the GITAM portal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={syncing ? "spin" : ""}>
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            {syncing ? "Syncing attendance..." : "Sync now"}
          </button>
          <Nav />
        </div>
      </header>

      {success && <p className="success-banner" role="status">{success}</p>}
      {syncMessage && <p className="success-banner" role="status">{syncMessage}</p>}

      {!data.exam_date && (
        <section className="setup-note">
          <div>
            <strong>Select a prediction target to calculate future classes.</strong>
            <span>Choose automatic sessional or a custom date.</span>
          </div>
          <Link to="/settings">Open Settings</Link>
        </section>
      )}

      <section className="metrics">
        <Metric
          label="Current attendance"
          value={`${overall.current_percentage}%`}
          hint={`${overall.present_classes} present · ${overall.absent_classes} absent · ${overall.total_classes} total`}
          status={getAttendanceStatus(overall.current_percentage, overall.target_percentage)}
        />
        <Metric label="Target" value={`${overall.target_percentage}%`} hint="Your goal" />
        <Metric
          label="Classes remaining"
          value={overall.future_classes}
          hint={data.exam_date ? <span>Until <strong className="date-highlight">{formatDate(data.exam_date)}</strong></span> : "Set target date"}
        />
        <Metric
          label="Projected attendance"
          value={`${overall.after_attending_all}%`}
          hint={overall.future_classes > 0 ? `If you attend all ${overall.future_classes} classes` : "No upcoming classes"}
          status={overall.target_reachable_in_window ? "good" : "warning"}
        />
        <Metric
          label="Safe skips"
          value={overall.can_skip}
          hint={`Can miss up to ${overall.can_skip} and stay ≥ ${overall.target_percentage}%`}
        />
        <Metric
          label="Must attend"
          value={overall.need_to_attend}
          hint={overall.need_to_attend === 0
            ? `Already above your ${overall.target_percentage}% target`
            : `Attend the next ${overall.need_to_attend} classes to reach ${overall.target_percentage}%`}
          status={overall.need_to_attend === 0 ? "good" : "warning"}
        />
      </section>

      <section className="calendar-info">
        <Link to="/settings" className="change-date-control">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          Change prediction date
        </Link>
      </section>

      <section className="dashboard-actions">
        <div>
          <h2>Subject details</h2>
          <p>View attendance, future classes, safe skips, and required attendance for every subject.</p>
        </div>
        <Link to="/subjects">View all subjects</Link>
      </section>

      {warnings.length > 0 && (
        <section className="warnings">
          <h2>Subject warnings</h2>
          {warnings.map((warning) => (
            <div key={warning.subject}>
              <strong>{warning.subject}</strong>
              <span>{warning.message} · {warning.percentage}%</span>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
