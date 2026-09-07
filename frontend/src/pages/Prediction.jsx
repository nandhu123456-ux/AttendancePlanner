import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { getPlanner } from "../api/api";
import "./Dashboard.css";

export default function Prediction() {
  const [data, setData] = useState(null);
  useEffect(() => { getPlanner(localStorage.getItem("student_id")).then(({ data }) => setData(data)); }, []);
  if (!data) return <main className="state"><div className="spinner" /></main>;
  const { overall } = data;
  return (
    <main className="dashboard">
      <header>
        <div>
          <div className="brand-header-inline">
            <svg width="24" height="24" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 4L4 14v12l16 10 16-10V14L20 4z" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M20 4v32M4 14l16 10 16-10M4 26l16-10 16 10" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <circle cx="20" cy="18" r="4" fill="currentColor"/>
            </svg>
            <p className="eyebrow">TRACK_75</p>
          </div>
          <h1>Prediction</h1>
          <p className="sync-note">Until {data.exam_date}</p>
        </div>
        <Nav />
      </header>
      <section className="prediction-card">
        <p>Projected attendance if you attend every scheduled class</p>
        <strong>{overall.after_attending_all}%</strong>
        <div className="prediction-bar">
          <i style={{ width: `${overall.current_percentage}%` }} />
          <b style={{ width: `${Math.max(0, overall.after_attending_all - overall.current_percentage)}%` }} />
        </div>
        <div className="prediction-labels">
          <span>Current: {overall.current_percentage}%</span>
          <span>Target: {overall.target_percentage}%</span>
          <span>Projected: {overall.after_attending_all}%</span>
        </div>
        {!overall.target_reachable_in_window && (
          <p className="form-error">Target not reachable by this date. Attend all classes or extend your target date.</p>
        )}
      </section>
    </main>
  );
}
