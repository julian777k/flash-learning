// sw.js
const CACHE = "flash-v7";    // 버전 바꿔주면 갱신
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  // 데이터(필요한 것만 추가, 또는 폴더 전체를 서버에서 제공)
  "./data/python_L1.json",
  "./data/python_L2.json",
  "./data/python_L3.json",
  "./data/python_L4.json",
  "./data/python_L5.json",
  "./data/mysql_L1.json",
  "./data/mysql_L2.json",
  "./data/mysql_L3.json",
  "./data/mysql_L4.json",
  "./data/mysql_L5.json",
  "./data/pandas_L1.json",
  "./data/pandas_L2.json",
  "./data/pandas_L3.json",
  "./data/pandas_L4.json",
  "./data/pandas_L5.json",
  "./data/english_vocab.json",
  "./data/english_coding.json",
  "./data/english_pattern.json",
  "./data/english_conversation.json",
];

self.addEventListener("install", e=>{
  e.waitUntil(
    caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())
  );
});
self.addEventListener("activate", e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.map(k=>k===CACHE?null:caches.delete(k))))
  );
  self.clients.claim();
});
self.addEventListener("fetch", e=>{
  const req = e.request;
  if(req.method !== "GET"){ return; }
  e.respondWith(
    caches.match(req).then(cached=>{
      if(cached) return cached;
      return fetch(req).then(res=>{
        const copy = res.clone();
        caches.open(CACHE).then(c=>c.put(req, copy));
        return res;
      }).catch(()=>caches.match("./index.html"));
    })
  );
});
