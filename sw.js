// sw.js 맨 위
// sw.js
const CACHE = "flash-v3"; // 버전업


const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./sw.js",
  "./data/english_vocab.json",
  "./data/english_coding.json",
  "./data/english_pattern.json",
  "./data/english_conversation.json"
  // 필요 시: python_L*.json, mysql_L*.json, pandas_L*.json도 여기에 추가 가능
];

self.addEventListener("install", (e)=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e)=>{
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (e)=>{
  e.respondWith(
    caches.match(e.request).then(r=> r || fetch(e.request))
  );
});
