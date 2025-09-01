// very small service worker (scope = current folder)
const CACHE = 'flash-learning-v3';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.map(k=>k!==CACHE && caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});
self.addEventListener('fetch', e=>{
  const req = e.request;
  // network first, cache fallback
  e.respondWith(
    fetch(req).then(r=>{
      const copy = r.clone();
      caches.open(CACHE).then(c=>c.put(req, copy)).catch(()=>{});
      return r;
    }).catch(()=>caches.match(req))
  );
});
