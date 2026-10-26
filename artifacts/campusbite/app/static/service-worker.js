const CACHE_VERSION = "campusbite-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGE_CACHE = `${CACHE_VERSION}-public-pages`;
const PUBLIC_SHELL = [
  "/offline",
  "/static/campusbite.css",
  "/static/campusbite.js",
  "/static/manifest.json",
  "/static/images/icon.svg",
  "/static/images/icon-192.png",
  "/static/images/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PUBLIC_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => !key.startsWith(CACHE_VERSION)).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/admin") || url.pathname.startsWith("/api/admin")) return;

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
    return;
  }

  const isPublicPage = request.mode === "navigate" &&
    (url.pathname === "/" || url.pathname === "/menu" ||
     url.pathname === "/weekly-menu" || url.pathname.startsWith("/food/"));
  const isPublicMenuData = url.pathname === "/api/menu/availability";
  if (!isPublicPage && !isPublicMenuData) return;

  event.respondWith(
    fetch(request).then((response) => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(PAGE_CACHE).then((cache) => cache.put(request, copy));
      }
      return response;
    }).catch(async () => {
      const cached = await caches.match(request);
      if (cached) {
        const headers = new Headers(cached.headers);
        headers.set("X-CampusBite-Stale", "1");
        headers.set("Cache-Control", "no-store");
        return new Response(await cached.arrayBuffer(), {
          status: cached.status,
          statusText: cached.statusText,
          headers
        });
      }
      if (isPublicPage) {
        const offline = await caches.match("/offline");
        if (offline) return offline;
      }
      return new Response(JSON.stringify({
        error: "Offline — menu and stock information may be outdated."
      }), {
        status: 503,
        headers: { "Content-Type": "application/json", "X-CampusBite-Stale": "1" }
      });
    })
  );
});
