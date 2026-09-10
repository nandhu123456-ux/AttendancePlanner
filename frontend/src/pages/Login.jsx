import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { loginInit, loginComplete, refreshCaptcha } from "../api/api";
import "./Login.css";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [captchaImage, setCaptchaImage] = useState(null);
  const [token, setToken] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const [savedUsers, setSavedUsers] = useState([]);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const captchaFetched = useRef(false);
  const debounceTimer = useRef(null);

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

    const fetchCaptcha = useCallback(async () => {
    if (!username.trim() || !password) return;
    setCaptchaLoading(true);
    setError("");
    try {
      const { data } = await loginInit({ username: username.trim(), password });
      setCaptchaImage(data.captcha_image);
      setToken(data.token);
      captchaFetched.current = true;
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load CAPTCHA. Please check your credentials.");
    } finally {
      setCaptchaLoading(false);
    }
  }, [username, password]);

  // Debounced auto-fetch CAPTCHA - only after user stops typing
  useEffect(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    if (username.trim() && password && !captchaImage && !captchaLoading && !captchaFetched.current) {
      debounceTimer.current = setTimeout(() => {
        fetchCaptcha();
      }, 800);
    }
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, [username, password, captchaImage, captchaLoading, fetchCaptcha]);

    const handleRefreshCaptcha = async () => {
    if (!token) return;
    setCaptchaLoading(true);
    setError("");
    try {
      const { data } = await refreshCaptcha({ token });
      setCaptchaImage(data.captcha_image);
      setCaptcha("");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not refresh CAPTCHA. Please try again.");
    } finally {
      setCaptchaLoading(false);
    }
  };

    // Handle username change - don't reset CAPTCHA immediately
  const handleUsernameChange = (e) => {
    setUsername(e.target.value);
    if (!e.target.value.trim()) {
      setCaptchaImage(null);
      setCaptcha("");
      setToken(null);
      captchaFetched.current = false;
    }
  };

  // Handle password change - don't reset CAPTCHA immediately
  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    if (!e.target.value) {
      setCaptchaImage(null);
      setCaptcha("");
      setToken(null);
      captchaFetched.current = false;
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!captcha.trim()) {
      setError("Please enter the CAPTCHA.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const { data } = await loginComplete({ token, captcha: captcha.trim() });
      localStorage.setItem("token", data.token);
      localStorage.setItem("student_id", data.student_id);
      // Save username for future quick login
      saveUser(username.trim());
      // The backend already refreshed the latest attendance during login.
      // If it could not, the user can log in again to refresh - attendance
      // is always re-fetched from GITAM at every successful login.
      if (!data.auto_sync) {
        sessionStorage.setItem(
          "predictionUpdated",
          "Signed in, but attendance could not be refreshed automatically. It will refresh on your next login."
        );
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
      <form className="login-card" onSubmit={handleLogin}>
        <div className="brand-header">
          <div className="brand-header-inline">
            <svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 4L4 14v12l16 10 16-10V14L20 4z" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M20 4v32M4 14l16 10 16-10M4 26l16-10 16 10" stroke="currentColor" strokeWidth="1.5" fill="none"/>
              <circle cx="20" cy="18" r="4" fill="currentColor"/>
            </svg>
            <h2 className="eyebrow">TRACK_75</h2>
          </div>
             <div className="login-footer">
                    <h2 className="login-copy">Made to help you stay on track ❤️</h2>
        </div>
        </div>

        <label>
           
          <input
            required
            type="text"
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={handleUsernameChange}
            placeholder="Gitam ID"
          />
        </label>

        <label>
          
          <div className="password-input-wrapper">
            <input
              required
              type={showPassword ? "text" : "password"}
              id="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={handlePasswordChange}
              placeholder="Gitam Password"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex="-1"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>
        </label>

        {(captchaImage || captchaLoading) && (
          <div className="captcha-section">
            <label className="captcha-label">CAPTCHA</label>
            {captchaImage ? (
              <div className="captcha-image-container">
                <img src={captchaImage} alt="CAPTCHA" className="captcha-image" />
                <button
                  type="button"
                  className="captcha-refresh"
                  onClick={handleRefreshCaptcha}
                  disabled={captchaLoading}
                  title="Refresh CAPTCHA"
                >
                  ↻
                </button>
              </div>
            ) : (
              <div className="captcha-loading">
                <div className="spinner"></div>
                Loading CAPTCHA...
              </div>
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
        )}

        {!captchaImage && !captchaLoading && username && password && (
          <button
            type="button"
            className="captcha-load-btn"
            onClick={fetchCaptcha}
          >
            Load CAPTCHA
          </button>
        )}

        {error && <p className="form-error" role="alert">{error}</p>}

        <button type="submit" disabled={loading || !captchaImage || !captcha.trim()}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
         
        <div className="trust-divider">
          <span className="trust-line">Your trust, our responsibility. 🤝</span>
        </div>
      </form>
    </main>
    );
}


