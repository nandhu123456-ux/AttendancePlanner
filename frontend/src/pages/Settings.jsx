import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Nav from "../components/Nav";
import StudentProfile from "../components/StudentProfile";
import PageHeader from "../components/PageHeader";
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
  const calendarInfo = settings.calendar_info || {};

  const formatDate = (iso) => {
    if (!iso) return "";
    const parsed = new Date(`${iso}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  };

  return (
    <main className="dashboard">
      <PageHeader title="Settings" />

      <Nav />

      <section className="dash-section settings-profile" aria-labelledby="profile-title">
        <div className="section-heading"><h2 id="profile-title">Student Profile</h2></div>
        <StudentProfile studentId={studentId} showEmail />
      </section>

      <form className="settings-form" onSubmit={save}>
        <section className="settings-section" aria-labelledby="prefs-title">
          <h2 id="prefs-title">Attendance Preferences</h2>
          <p className="section-desc">Set the minimum attendance you want to maintain.</p>
          <label>
            Target attendance percentage
            <input
              type="number"
              min="1"
              max="100"
              value={settings.target_percentage}
              onChange={(e) => setSettings({ ...settings, target_percentage: e.target.value })}
              required
            />
          </label>
        </section>

        <section className="settings-section" aria-labelledby="date-title">
          <h2 id="date-title">Prediction Date</h2>
          <p className="section-desc">Choose the date used to project your future classes.</p>
          <label>
            Target date
            <input
              type="date"
              min={minDate}
              max={maxDate}
              value={customDate}
              onChange={(e) => setCustomDate(e.target.value)}
              required
            />
          </label>

          <div className="calendar-facts">
            <div className="fact">
              <span className="fact-label">Academic year</span>
              <span className="fact-value">
                {calendarInfo.academic_year
                  ? `${calendarInfo.academic_year} · ${calendarInfo.semester_type || "ODD"}`
                  : "No academic calendar loaded."}
              </span>
            </div>
            {datePicker.max_date && (
              <div className="fact">
                <span className="fact-label">Prediction window</span>
                <span className="fact-value">{formatDate(datePicker.min_date)} → {formatDate(datePicker.max_date)}</span>
              </div>
            )}
          </div>

          {message && <p className="form-error">{message}</p>}

          <button className="primary-btn" disabled={saving} type="submit">
            {saving ? "Calculating…" : "Calculate Prediction"}
          </button>
        </section>
      </form>

      <section className="settings-section account-section" aria-labelledby="account-title">
        <h2 id="account-title">Security &amp; Account</h2>
        <p className="section-desc">Sign out of TRACK_75 on this device.</p>
        <button className="quiet" type="button" onClick={logout}>Sign out on this device</button>
      </section>
    </main>
  );
}
