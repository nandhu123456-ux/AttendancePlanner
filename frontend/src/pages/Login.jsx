import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginInit, loginComplete, refreshCaptcha, sync } from "../api/api";
import "./Login.css";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [captchaImage, setCaptchaImage] = useState(null);
  const [token, setToken] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const navigate = useNavigate();

  const handleContinue = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await loginInit({ username: username.trim(), password });
      setCaptchaImage(data.captcha_image);
      setToken(data.token);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load CAPTCHA. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshCaptcha = async () => {
    setError("");
    setLoading(true);
    try {
      const { data } = await refreshCaptcha({ token });
      setCaptchaImage(data.captcha_image);
      setCaptcha("");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not refresh CAPTCHA. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setStep(1);
    setCaptcha("");
    setCaptchaImage(null);
    setToken(null);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await loginComplete({ token, captcha: captcha.trim() });
      localStorage.setItem("token", data.token);
      localStorage.setItem("student_id", data.student_id);
      await sync(data.student_id);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Please check your CAPTCHA.");
      localStorage.removeItem("token");
      localStorage.removeItem("student_id");
      if (err.response?.status === 401) {
        handleRefreshCaptcha();
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={step === 1 ? handleContinue : handleLogin}>
        <p className="eyebrow">STUDENT PORTAL</p>
        <h1>Attendance Planner</h1>
        <p className="login-copy">See your attendance outlook before your next class.</p>

        <label>
          Student ID
          <input
            required
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={step === 2}
          />
        </label>

        {step === 1 && (
          <label>
            Password
            <input
              required
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        )}

        {step === 2 && (
          <>
            <button type="button" className="text-button" onClick={handleBack}>
              ← Back to credentials
            </button>

            <div className="captcha-section">
              <p className="captcha-label">Enter the characters shown below:</p>
              {captchaImage ? (
                <div className="captcha-image-container">
                  <img src={captchaImage} alt="CAPTCHA" className="captcha-image" />
                  <button type="button" className="captcha-refresh" onClick={handleRefreshCaptcha} title="Refresh CAPTCHA">
                    ↻
                  </button>
                </div>
              ) : (
                <div className="captcha-loading">Loading CAPTCHA...</div>
              )}
              <input
                required
                autoComplete="off"
                placeholder="Enter CAPTCHA"
                value={captcha}
                onChange={(e) => setCaptcha(e.target.value)}
                className="captcha-input"
                maxLength={32}
              />
            </div>

            <label className="password-display">
              Password:
              <span className="password-mask">{"•".repeat(Math.min(password.length, 12))}</span>
            </label>
          </>
        )}

        {error && <p className="form-error" role="alert">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading
            ? step === 1
              ? "Loading CAPTCHA..."
              : "Signing in..."
            : step === 1
              ? "Continue"
              : "Sign in"}
        </button>

        <small>Your portal password is encrypted server-side so attendance can refresh securely.</small>
      </form>
    </main>
  );
}
