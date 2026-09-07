import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import { getSettings, updateSettings, setTargetType } from "../api/api";
import "./Dashboard.css";

export default function Settings() {
  const navigate = useNavigate();
  const studentId = localStorage.getItem("student_id");
  const [settings, setSettings] = useState(null);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [customDate, setCustomDate] = useState("");

  useEffect(() => {
    getSettings(studentId).then(({ data }) => {
      setSettings(data);
      if (data.custom_target_date) setCustomDate(data.custom_target_date);
    }).catch(() => setMessage("Could not load preferences."));
  }, [studentId]);

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      if (!customDate) {
        setMessage("Please select a target date.");
        return;
      }
      await setTargetType(studentId, { target_type: "custom", custom_target_date: customDate });
      await updateSettings(studentId, { ...settings, target_percentage: Number(settings.target_percentage) });
      sessionStorage.setItem("predictionUpdated", "Prediction recalculated and preferences saved.");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setMessage(err.response?.data?.detail || "Unable to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const logout = () => { localStorage.clear(); navigate("/login"); };
  if (!settings) return <main className="state"><h1>Settings unavailable</h1><p>{message || "Unable to load preferences. Please sign in again."}</p></main>;

  const datePicker = settings.date_picker || {};
  const minDate = datePicker.min_date || new Date().toISOString().split('T')[0];
  const maxDate = datePicker.max_date || new Date().toISOString().split('T')[0];

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
          <h1>Settings</h1>
        </div>
        <Nav />
      </header>
      <form className="panel settings" onSubmit={save}>
        <label>Student ID<input value={studentId || ""} disabled /></label>
        <label>Target attendance percentage<input type="number" min="1" max="100" value={settings.target_percentage} onChange={(e) => setSettings({ ...settings, target_percentage: e.target.value })} required /></label>

        <label>Target date<input type="date" min={minDate} max={maxDate} value={customDate} onChange={(e) => setCustomDate(e.target.value)} required /></label>

        <p className="muted">
          {settings.calendar_info?.academic_year
            ? `Academic year: ${settings.calendar_info.academic_year} (${settings.calendar_info.semester_type || "ODD"})`
            : "No academic calendar loaded."}
          {datePicker.max_date ? ` · Valid range: ${datePicker.min_date} to ${datePicker.max_date}` : ""}
        </p>

        {/* Notifications toggle hidden from UI */}
        {message && <p className="form-error">{message}</p>}
        <button disabled={saving} type="submit">{saving ? "Calculating…" : "Calculate prediction"}</button>
        <button className="quiet" type="button" onClick={logout}>Sign out on this device</button>
      </form>
    </main>
  );
}
