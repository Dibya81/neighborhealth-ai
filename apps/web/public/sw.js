// Offline-friendly service worker for low-bandwidth use:
//  * app shell + ward boundaries: cache-first
//  * forecast / ward risk API: network-first, falling back to the last copy (so the map still works offline)
const VERSION = "nh-v2-1";
const SHELL = ["/", "/map", "/forecast", "/report", "/alerts", "/assistant", "/data/wards.geojson", "/icons/icon-192.png"];
const API_CACHEABLE = [/\/v2\/forecast$/, /\/v2\/wards\/risk/, /\/v2\/city$/, /\/v2\/model$/];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (API_CACHEABLE.some((re) => re.test(url.pathname))) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req)),
    );
    return;
  }

  if (url.origin === self.location.origin && (url.pathname.startsWith("/_next/static") || url.pathname.startsWith("/data/") || url.pathname.startsWith("/icons/"))) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(VERSION).then((c) => c.put(req, copy));
      return res;
    })));
    return;
  }

  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match(req).then((hit) => hit || caches.match("/"))));
  }
});
