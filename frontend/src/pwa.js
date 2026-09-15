/*
 * PWA support for TRACK_75: service worker registration + simple update handling.
 *
 * When a new version is deployed, the updated service worker installs,
 * activates immediately (SKIP_WAITING) and the page reloads once, so users
 * never stay stuck on an old frontend version.
 */
let reloading = false;

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        // An update may already be waiting when the page loads.
        if (registration.waiting) activateUpdate(registration.waiting);

        registration.addEventListener("updatefound", () => {
          const installing = registration.installing;
          if (!installing) return;
          installing.addEventListener("statechange", () => {
            // Only activate an update on top of an existing SW (first install
            // needs no reload — the page already runs the latest version).
            if (installing.state === "installed" && navigator.serviceWorker.controller) {
              activateUpdate(installing);
            }
          });
        });
      })
      .catch(() => {
        /* SW registration is best-effort; never block the app. */
      });

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    });
  });
}

function activateUpdate(worker) {
  worker.postMessage("SKIP_WAITING");
}
