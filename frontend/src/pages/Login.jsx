import { useState, useEffect } from "react";
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
  const [savedUsers, setSavedUsers] = useState([]);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const navigate = useNavigate();

  // Load saved usernames from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("saved_users");
    if (saved) {
      try {
        setSavedUsers(JSON.parse(saved));
      } catch {
        setSavedUsers([]);
      }
    }
  }, []);

  // Save username to localStorage
  const saveUser = (user) => {
    if (!user) return;
    const updated = [user, ...savedUsers.filter(u => u !== user)].slice(0, 5);
    setSavedUsers(updated);
    localStorage.setItem("saved_users", JSON.stringify(updated));
  };

  // Remove username from saved list
  const removeUser = (userToRemove) => {
    const updated = savedUsers.filter(u => u !== userToRemove);
    setSavedUsers(updated);
    localStorage.setItem("saved_users", JSON.stringify(updated));
  };

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
      // Save username for future quick login
      saveUser(username.trim());
      // The backend already refreshed the latest attendance during login
      // (data.auto_sync). Only fall back to an explicit sync if the server
      // could not run it. Either way, never log the user out over a sync
      // problem - attendance will refresh again on the next login.
      if (!data.auto_sync) {
        try {
          await sync(data.student_id);
        } catch {
          sessionStorage.setItem(
            "predictionUpdated",
            "Signed in, but attendance could not be refreshed automatically. It will refresh on your next login."
          );
        }
      }
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
        <div className="brand-header">
          <div className="brand-logo">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 4L4 14v12l16 10 16-10V14L20 4z" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M20 4v32M4 14l16 10 16-10M4 26l16-10 16 10" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <circle cx="20" cy="18" r="4" fill="currentColor"/>
            </svg>
          </div>
          <p className="eyebrow">TRACK_75</p>
        </div>
        <h1>Welcome Back</h1>
        <p className="login-copy">Sign in to track your attendance and plan ahead.</p>

        <p className="login-info">
          Enter your GITAM username and password 🔑 — the same credentials you use to open your
          GITAM student portal. They are used only to sign in there and fetch your live attendance.
        </p>

        <label>
          Student ID
          <div className="input-with-dropdown">
            <input
              required
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onFocus={() => setShowUserDropdown(true)}
              onBlur={() => setTimeout(() => setShowUserDropdown(false), 200)}
              disabled={step === 2}
              placeholder="Enter your student ID"
            />
            {step === 1 && savedUsers.length > 0 && showUserDropdown && (
              <div className="saved-users-dropdown">
                <div className="saved-users-header">Recent accounts</div>
                {savedUsers.map((user) => (
                  <div
                    key={user}
                    className="saved-user-item"
                    onMouseDown={() => {
                      setUsername(user);
                      setShowUserDropdown(false);
                    }}
                  >
                    <span className="user-icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                    </span>
                    <span className="user-name">{user}</span>
                    <button
                      type="button"
                      className="remove-user-btn"
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        removeUser(user);
                      }}
                      title="Remove from list"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </label>

        {step === 1 && (
          <label>
            Password
            <input
              required
              type="password"
              id="password"
              name="password"
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
                type="text"
                name="captcha"
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

        <small>Your password is encrypted and used only to sign in to the GITAM portal.</small>
      </form>
    </main>
  );
}

