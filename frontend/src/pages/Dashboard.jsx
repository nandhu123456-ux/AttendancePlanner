import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import StudentProfile from "../components/StudentProfile";
import PageHeader from "../components/PageHeader";
import { getPlanner } from "../api/api";
import "./Dashboard.css";

const Metric = ({ label, value, hint, status, hero = false }) => (
  <article className={`metric${hero ? " metric-hero" : ""}${status ? ` metric-${status}` : ""}`}>
    <p>{label}</p>
    <strong>{value}</strong>
    {hint && <span>{hint}</span>}
  </article>
);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const studentId = localStorage.getItem("student_id");
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
  const calInfo = data.calendar_info || {};

  // Status label derived only from existing attendance/target values.
  const status = overall.current_percentage >= overall.target_percentage
    ? "good"
    : overall.current_percentage >= overall.target_percentage - 10 ? "warning" : "danger";
  const statusLabel = { good: "On track", warning: "Needs attention", danger: "At risk" }[status];

  const formatDate = (iso) => {
    const parsed = new Date(iso);
    return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  return (
    <main className="dashboard">
      <PageHeader title="Dashboard" actions={<StudentProfile studentId={studentId} />}>
        {calInfo.sessional && (
          <p className="sessional-badge">
            {calInfo.academic_year && (
              <span className="academic-year-badge">{calInfo.academic_year} ({calInfo.semester_type || "ODD"})</span>
            )}
            <span>Targeting {calInfo.sessional.replace("_", "-").toUpperCase()}</span>
            {calInfo.sessional_end ? ` · ends ${calInfo.sessional_end}` : ""}
          </p>
        )}
      </PageHeader>

      <Nav />

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

      <section className="dash-section" aria-labelledby="overview-title">
        <div className="section-heading"><h2 id="overview-title">Attendance Overview</h2></div>
        <div className="overview-grid">
          <Metric
            hero
            label="Current attendance"
            value={`${overall.current_percentage}%`}
            hint={`${overall.present_classes} present · ${overall.absent_classes} absent · ${overall.total_classes} total`}
            status={status}
          />
          <Metric label="Target" value={`${overall.target_percentage}%`} hint="Your goal" />
          <Metric label="Status" value={statusLabel} hint={`Against ${overall.target_percentage}% target`} status={status} />
        </div>
      </section>

      <section className="dash-section" aria-labelledby="upcoming-title">
        <div className="section-heading">
          <h2 id="upcoming-title">Upcoming Classes</h2>
          <Link className="section-link" to="/settings">Change date</Link>
        </div>
        <div className="projection-grid">
          <Metric
            label="Classes remaining"
            value={overall.future_classes}
            hint={data.exam_date ? <>Until <span className="date-highlight">{formatDate(data.exam_date)}</span></> : "Set a target date"}
          />
          <Metric
            label="Projected attendance"
            value={`${overall.after_attending_all}%`}
            hint={overall.future_classes > 0 ? `If you attend all ${overall.future_classes} classes` : "No upcoming classes"}
            status={overall.target_reachable_in_window ? "good" : "warning"}
          />
        </div>
      </section>

      <section className="dash-section" aria-labelledby="planning-title">
        <div className="section-heading"><h2 id="planning-title">Attendance Planning</h2></div>
        <div className="planning-grid">
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
        </div>
      </section>

      <div className="info-ticker" role="status">
        <span className="info-ticker-icon" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </span>
        <div className="info-ticker-viewport">
          <div className="info-ticker-track">
            <span>Change the prediction date in <Link to="/settings">Settings</Link></span>
            <span>Attendance calculations are updated accurately at every login</span>
          </div>
        </div>
      </div>

      <section className="dash-link-card">
        <div>
          <h2>Subject details</h2>
          <p>Attendance, future classes, safe skips and required attendance for every subject.</p>
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
