import { useEffect, useState } from "react";

const DISMISS_KEY = "pwa-install-dismissed";

/**
 * Subtle, dismissible "Install TRACK_75" banner using the standard browser
 * install flow (beforeinstallprompt). It is never shown repeatedly after
 * dismissal, hides once installed, and does not interfere with the app.
 */
export default function InstallPrompt() {
  const [promptEvent, setPromptEvent] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Already installed as a PWA (standalone display) -> nothing to offer.
    if (window.matchMedia("(display-mode: standalone)").matches) return;
    if (localStorage.getItem(DISMISS_KEY) === "1") return;

    const onPrompt = (event) => {
      event.preventDefault();
      setPromptEvent(event);
      setVisible(true);
    };
    const onInstalled = () => setVisible(false);

    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!visible || !promptEvent) return null;

  const install = async () => {
    promptEvent.prompt();
    await promptEvent.userChoice;
    setPromptEvent(null);
    setVisible(false);
  };

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, "1");
    setVisible(false);
  };

  return (
    <div className="pwa-install" role="dialog" aria-label="Install TRACK_75">
      <img src="/icons/icon-192.png" alt="" className="pwa-install-icon" />
      <div className="pwa-install-text">
        <strong>Install TRACK_75</strong>
        <span>Add to your home screen for the full experience</span>
      </div>
      <button type="button" className="pwa-install-btn" onClick={install}>
        Install
      </button>
      <button type="button" className="pwa-install-dismiss" onClick={dismiss} aria-label="Dismiss install prompt">
        &#10005;
      </button>
    </div>
  );
}
