/* Lightweight runtime cache SW (network-first) */
const CACHE = "flash-v12";   // ← 버전 올리면 강제 갱신됨

const SHELL = [
  "./",
  "./index.html",
  "./sw.js",
  "./manifest.webmanifest.json", // 현재 파일명 유지
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", e=>{
  e.waitUntil(
    caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())
  );
});
self.addEventListener("activate", e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.map(k=>k===CACHE?null:caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

// same-origin GET → network first, cache fallback
self.addEventListener("fetch", e=>{
  const url = new URL(e.request.url);
  if (e.request.method!=="GET" || url.origin!==location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then(res=>{
        const copy = res.clone();
        caches.open(CACHE).then(c=>c.put(e.request, copy));
        return res;
      })
      .catch(()=>caches.match(e.request))
  );
});
