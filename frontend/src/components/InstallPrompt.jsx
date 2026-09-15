import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

const DISMISS_KEY = "track75-install-dismissed";

/*
 * The deferred native install prompt is captured at MODULE level so an early
 * `beforeinstallprompt` (Chrome/Edge often fire it right after page load,
 * possibly before React has rendered anything) is never lost. The card
 * itself is only ever displayed for authenticated users — visibility is
 * derived from the current route on each render, not from when the event
 * happens to fire.
 */
let deferredPrompt = null;

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    window.dispatchEvent(new Event("track75:installavailable"));
  });
}

function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

/**
 * Subtle, dismissible "Install TRACK_75" card using the standard browser
 * install flow. It is re-evaluated after every successful login (i.e. on
 * navigation away from /login into the authenticated app) without requiring
 * a refresh.
 *
 * Dismissal is tied to the current login session: the dismissed record
 * stores the auth token that was active when it was dismissed, so it no
 * longer applies after logout + a new login (new token), while a page
 * refresh in the same session keeps it dismissed. No permanent
 * "never show again" flag is stored. Once the app is installed or runs in
 * standalone mode, the card never appears.
 */
export default function InstallPrompt() {
  const location = useLocation();
  const [promptAvailable, setPromptAvailable] = useState(() => deferredPrompt !== null);
  const [installed, setInstalled] = useState(() => isStandalone());
  const [hidden, setHidden] = useState(false); // dismissed / accepted during this visit

  // Evaluate the install suggestion against the EXISTING authenticated app
  // state (token + route), exactly like ProtectedRoute does. Derived during
  // render, so the card appears immediately after a successful login — no
  // refresh needed, and navigating Dashboard/Settings never re-triggers it
  // once dismissed.
  const token = localStorage.getItem("token");
  const authenticated = location.pathname !== "/login" && !!token;
  const sessionDismissed = !!token && sessionStorage.getItem(DISMISS_KEY) === token;
  const visible = authenticated && !installed && !sessionDismissed && !hidden;

  // Keep native-install availability and installed state in sync (external
  // browser events only — these callbacks fire outside of render).
  useEffect(() => {
    const onAvailable = () => setPromptAvailable(true);
    const onInstalled = () => {
      deferredPrompt = null;
      setPromptAvailable(false);
      setInstalled(true);
      setHidden(true);
    };
    const mq = window.matchMedia("(display-mode: standalone)");
    const onModeChange = (e) => {
      if (e.matches) onInstalled();
    };

    window.addEventListener("track75:installavailable", onAvailable);
    window.addEventListener("appinstalled", onInstalled);
    mq.addEventListener?.("change", onModeChange);
    return () => {
      window.removeEventListener("track75:installavailable", onAvailable);
      window.removeEventListener("appinstalled", onInstalled);
      mq.removeEventListener?.("change", onModeChange);
    };
  }, []);

  if (!visible) return null;

  const install = async () => {
    const prompt = deferredPrompt;
    if (!prompt) return; // never fake the native install flow
    prompt.prompt();
    try {
      const choice = await prompt.userChoice;
      if (choice?.outcome === "accepted") {
        setInstalled(true);
        setHidden(true);
      }
    } finally {
      deferredPrompt = null;
      setPromptAvailable(false);
    }
  };

  const dismiss = () => {
    // Dismissal applies to the current login only (sessionStorage keyed to
    // the current auth token — never a permanent localStorage flag).
    sessionStorage.setItem(DISMISS_KEY, token);
    setHidden(true);
  };

  return (
    <div className="pwa-install" role="dialog" aria-label="Install TRACK_75">
      <img src="/icons/icon-192.png" alt="" className="pwa-install-icon" />
      <div className="pwa-install-text">
        <strong>Install TRACK_75</strong>
        <span>Get quick access from your home screen.</span>
      </div>
      {promptAvailable ? (
        <button type="button" className="pwa-install-btn" onClick={install}>
          Install
        </button>
      ) : (
        <span className="pwa-install-hint">Browser menu &rarr; &ldquo;Install app&rdquo;</span>
      )}
      <button type="button" className="pwa-install-dismiss" onClick={dismiss} aria-label="Dismiss install prompt">
        &#10005;
      </button>
    </div>
  );
}

