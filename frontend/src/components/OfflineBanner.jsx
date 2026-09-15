import { useEffect, useState } from "react";

/**
 * Small fixed banner shown while the device is offline. It never shows or
 * implies cached attendance data — it only tells the user the app is offline.
 */
export default function OfflineBanner() {
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div className="pwa-offline" role="status">
      You&rsquo;re offline. Reconnect to update your attendance.
    </div>
  );
}
