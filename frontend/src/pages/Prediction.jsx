import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import PageHeader from "../components/PageHeader";
import { getPlanner } from "../api/api";
import "./Dashboard.css";

export default function Prediction() {
  const [data, setData] = useState(null);
  useEffect(() => { getPlanner(localStorage.getItem("student_id")).then(({ data }) => setData(data)); }, []);
  if (!data) return <main className="state"><div className="spinner" /></main>;
  const { overall } = data;
  return (
    <main className="dashboard">
      <PageHeader title="Prediction">
        <p className="sync-note">Until {data.exam_date}</p>
      </PageHeader>
      <Nav />
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
