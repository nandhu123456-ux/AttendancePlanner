/*
 * TRACK_75 service worker.
 *
 * Caches ONLY the static application shell so the app can open offline.
 * It never intercepts API/data requests (login, planner, attendance,
 * settings, user info, ...) or cross-origin requests — those always go
 * straight to the network so no sensitive or dynamic data is ever cached.
 *
 * Update strategy: navigations are network-first, so a new deploy is
 * picked up on the next visit. Vite's hashed /assets/* files are
 * immutable, so they are served cache-first.
 */
const VERSION = "v1";
const SHELL_CACHE = `track75-shell-${VERSION}`;
const ASSET_CACHE = `track75-assets-${VERSION}`;

const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
  "/icons/apple-touch-icon.png",
];

// Same-origin API/data paths that must NEVER be served from (or written to) a cache.
const API_PATHS = [
  "/login",
  "/planner",
  "/history",
  "/settings",
  "/custom-adjustment",
  "/target-type",
  "/userinfo",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => n.startsWith("track75-") && n !== SHELL_CACHE && n !== ASSET_CACHE)
          .map((n) => caches.delete(n))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING" || event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

function isApiDataRequest(url) {
  if (url.origin !== self.location.origin) return false;
  return API_PATHS.some((p) => url.pathname === p || url.pathname.startsWith(p + "/"));
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Never touch cross-origin requests (e.g. VITE_API_URL backend, fonts) or API/data routes.
  if (url.origin !== self.location.origin || isApiDataRequest(url)) return;

  if (request.mode === "navigate") {
    // Network-first: new deployments are always picked up when online.
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(request);
          const cache = await caches.open(SHELL_CACHE);
          cache.put("/index.html", fresh.clone());
          return fresh;
        } catch {
          // Offline: serve the cached app shell.
          const cached = (await caches.match("/index.html")) || (await caches.match("/"));
          return cached || new Response("Offline", { status: 503, statusText: "Offline" });
        }
      })()
    );
    return;
  }

  // Vite hashed assets are immutable -> cache-first.
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        const fresh = await fetch(request);
        if (fresh && fresh.status === 200) {
          const cache = await caches.open(ASSET_CACHE);
          cache.put(request, fresh.clone());
        }
        return fresh;
      })()
    );
    return;
  }

  // Other same-origin static files -> stale-while-revalidate.
  event.respondWith(
    (async () => {
      const cache = await caches.open(ASSET_CACHE);
      const cached = await cache.match(request);
      const network = fetch(request)
        .then((res) => {
          if (res && res.status === 200) cache.put(request, res.clone());
          return res;
        })
        .catch(() => null);
      return cached || (await network) || Response.error();
    })()
  );
});
