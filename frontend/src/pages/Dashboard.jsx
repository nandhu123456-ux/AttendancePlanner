import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import { Link } from "react-router-dom";
import { getPlanner } from "../api/api";
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

  const logout = () => { localStorage.clear(); navigate("/login"); };

  if (error) return <main className="state"><h1>Attendance Planner</h1><p>{error}</p><button onClick={logout}>Return to login</button></main>;
  if (!data) return <main className="state"><div className="spinner" /><p>Building your attendance plan…</p></main>;

  const { overall, warnings } = data;
  const syncDate = data.sync_status?.last_portal_sync_at;
  const syncLabel = "Portal data last updated";
  const calInfo = data.calendar_info || {};

  const getAttendanceStatus = (pct, target) => {
    if (pct >= target) return "good";
    if (pct >= target - 10) return "warning";
    return "danger";
  };

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">YOUR ATTENDANCE OUTLOOK</p>
          <h1>Attendance Planner</h1>
          {calInfo.sessional && (
            <p className="sessional-badge">
              Targeting {calInfo.sessional.replace("_", "-").toUpperCase()}
              {calInfo.sessional_end ? ` · ends ${calInfo.sessional_end}` : ""}
            </p>
          )}
          <p className="sync-note">{syncDate ? `${syncLabel}: ${new Date(syncDate).toLocaleString()}` : "No portal data has been synced yet."}</p>
        </div>
        <div className="nav-actions">
          <Nav />
          <button className="quiet" onClick={logout}>Sign out</button>
        </div>
      </header>

      {success && <p className="success-banner" role="status">{success}</p>}

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
          hint={`Present ${overall.present_classes} / Total ${overall.total_classes} · Absent ${overall.absent_classes}`}
          status={getAttendanceStatus(overall.current_percentage, overall.target_percentage)}
        />
        <Metric label="Target" value={`${overall.target_percentage}%`} hint="Your goal" />
        <Metric
          label="Classes remaining"
          value={overall.future_classes}
          hint={data.exam_date ? `Through ${data.exam_date}` : "Set target date"}
        />
        <Metric
          label="After attending all"
          value={`${overall.after_attending_all}%`}
          hint="Projected final"
          status={overall.target_reachable_in_window ? "good" : "warning"}
        />
        <Metric
          label="Safe skips"
          value={overall.can_skip}
          hint="While meeting target"
        />
        <Metric
          label="Must attend"
          value={overall.need_to_attend}
          hint={overall.need_to_attend === 0 ? "Already at target" : "To reach target"}
          status={overall.need_to_attend === 0 ? "good" : "warning"}
        />
      </section>

      {calInfo.blocked_dates_count > 0 && (
        <section className="calendar-info">
          <p className="muted">{calInfo.blocked_dates_count} non-instructional days excluded from future classes.</p>
        </section>
      )}

      <section className="dashboard-actions">
        <div>
          <h2>Subject details</h2>
          <p>View attendance, future classes, safe skips, and required attendance for every subject.</p>
        </div>
        <Link to="/subjects">View subject details</Link>
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
