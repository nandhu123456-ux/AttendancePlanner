import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { getPlanner } from "../api/api";
import "./Dashboard.css";

export default function Prediction() {
  const [data, setData] = useState(null);
  useEffect(() => { getPlanner(localStorage.getItem("student_id")).then(({ data }) => setData(data)); }, []);
  if (!data) return <main className="state"><div className="spinner" /></main>;
  const { overall } = data;
  return <main className="dashboard"><header><div><p className="eyebrow">UNTIL {data.exam_date}</p><h1>Prediction</h1></div><Nav /></header><section className="prediction-card"><p>Projected attendance if you attend every scheduled class through your exam date</p><strong>{overall.after_attending_all}%</strong><div className="prediction-bar"><i style={{ width: `${overall.current_percentage}%` }} /><b style={{ width: `${Math.max(0, overall.after_attending_all - overall.current_percentage)}%` }} /></div><div><span>Current: {overall.current_percentage}%</span><span>Target: {overall.target_percentage}%</span><span>After attending all: {overall.after_attending_all}%</span></div>{!overall.target_reachable_in_window && <p className="form-error">The target is not reachable before this exam date. Attend every upcoming class and extend the date if possible.</p>}</section></main>;
}
