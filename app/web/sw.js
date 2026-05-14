/**
 * HireFlow AI — service worker.
 *
 * Strategy:
 *   - Static assets (HTML, CSS, JS, icons, manifest) → cache-first.
 *   - API requests (everything under the same origin that isn't a
 *     static asset) → network-first with a stale-cache fallback so
 *     the app stays usable offline (read-only).
 *
 * Bump CACHE_VERSION on any deployable change to invalidate the old
 * cache on the user's device.
 */
const CACHE_VERSION = 'hireflow-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/css/style.css',
  '/js/app.js',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

function isStaticAsset(url) {
  return (
    url.pathname === '/' ||
    url.pathname.endsWith('.html') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.webmanifest') ||
    url.pathname.startsWith('/icons/') ||
    url.pathname.startsWith('/css/') ||
    url.pathname.startsWith('/js/')
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // only cache idempotent reads
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (isStaticAsset(url)) {
    // cache-first
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((resp) => {
          if (resp.ok) {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, clone));
          }
          return resp;
        });
      })
    );
    return;
  }

  // network-first, fall back to last-known-good cache
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, clone));
        }
        return resp;
      })
      .catch(() => caches.match(req))
  );
});
