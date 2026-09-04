import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { getPlanner } from "../api/api";
import "./Dashboard.css";

export default function Subjects() {
  const [subjects, setSubjects] = useState(null);
  useEffect(() => { getPlanner(localStorage.getItem("student_id")).then(({ data }) => setSubjects(data.subjects)); }, []);
  return <main className="dashboard"><header><div><p className="eyebrow">COURSE-LEVEL PLANNING</p><h1>Subjects</h1></div><Nav /></header>{!subjects ? <div className="spinner" /> : <section className="subject-grid">{Object.entries(subjects).map(([name, item]) => <article className="subject-card" key={name}><p className="eyebrow">{item.course_code || "COURSE"}</p><h2>{name}</h2><strong>{item.current_percentage}%</strong><div className="subject-stats"><span>Conducted <b>{item.conducted}</b></span><span>Present <b>{item.present}</b></span><span>Absent <b>{item.absent}</b></span><span>Future <b>{item.future_classes}</b></span><span>Safe skips <b>{item.safe_skips}</b></span><span>Required <b>{item.required_attendance}</b></span></div><p className={item.current_percentage >= 75 ? "status good" : "status risk"}>{item.current_percentage >= 75 ? "On track" : "Below target"}</p></article>)}</section>}</main>;
}
