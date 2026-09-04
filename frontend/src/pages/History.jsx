import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { getHistory } from "../api/api";
import "./Dashboard.css";

export default function History() {
  const [records, setRecords] = useState(null); const [error, setError] = useState("");
  useEffect(() => { const id = localStorage.getItem("student_id"); getHistory(id).then(({ data }) => setRecords(data.records)).catch((err) => setError(err.response?.data?.detail || "Unable to load history.")); }, []);
  return <main className="dashboard"><header><div><p className="eyebrow">SYNC ACTIVITY</p><h1>History</h1></div><Nav /></header>{error && <p className="form-error">{error}</p>}{!records ? <div className="spinner" /> : <section className="panel"><div className="table-wrap"><table><thead><tr><th>Synced at</th><th>Subjects changed</th><th>Timetable changes</th></tr></thead><tbody>{records.map((record, index) => <tr key={`${record.timestamp}-${index}`}><td>{record.timestamp ? new Date(record.timestamp).toLocaleString() : "—"}</td><td>{record.subjectsChanged || 0}</td><td>{record.timetableChanged || 0}</td></tr>)}</tbody></table></div></section>}</main>;
}
