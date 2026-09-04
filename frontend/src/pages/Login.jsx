import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, sync } from "../api/api";
import "./Login.css";

export default function Login() {
  const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const submit = async (event) => {
    event.preventDefault(); setError(""); setLoading(true);
    try {
      const { data } = await login({ username: username.trim(), password });
      localStorage.setItem("token", data.token); localStorage.setItem("student_id", data.student_id);
      await sync(data.student_id);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "We could not sign you in. Please try again.");
      localStorage.removeItem("token"); localStorage.removeItem("student_id");
    } finally { setLoading(false); }
  };
  return <main className="login-shell"><form className="login-card" onSubmit={submit}>
    <p className="eyebrow">STUDENT PORTAL</p><h1>Attendance Planner</h1>
    <p className="login-copy">See your attendance outlook before your next class.</p>
    <label>Student ID<input required autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
    <label>Password<input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button type="submit" disabled={loading}>{loading ? "Connecting securely…" : "Sign in"}</button>
    <small>Your portal password is encrypted server-side so attendance can refresh securely.</small>
  </form></main>;
}
