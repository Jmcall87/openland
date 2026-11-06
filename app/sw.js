// OpenLand PWA service worker: app works offline after the first visit.
const V = 'ol-v531-1'
const SHELL = ['./', './index.html', './manifest.webmanifest', './favicon.svg', './icons/icon-192.png', './icons/icon-512.png', './apple-touch-icon.png']
self.addEventListener('install', (e) => { e.waitUntil(caches.open(V).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())) })
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V && k.startsWith('ol-v')).map((k) => caches.delete(k)))).then(() => self.clients.claim())) })
const LONG = /^https:\/\/(unpkg\.com\/@ffmpeg|cdn\.jsdelivr\.net\/(fontsource|npm\/@huggingface|npm\/onnxruntime))/
self.addEventListener('fetch', (e) => {
  const r = e.request; if (r.method !== 'GET') return
  const u = new URL(r.url)
  if (/\/(mcp-callback|oauth)\.html$/.test(u.pathname)) return
  if (u.origin === location.origin) {
    if (r.mode === 'navigate') { e.respondWith(fetch(r).then((res) => { const c = res.clone(); caches.open(V).then((x) => x.put('./index.html', c)); return res }).catch(() => caches.match('./index.html'))); return }
    // hashed assets, v86 images, skills: cache-first
    e.respondWith(caches.match(r).then((hit) => hit || fetch(r).then((res) => { if (res.ok && res.status === 200) { const c = res.clone(); caches.open(V).then((x) => x.put(r, c)) } return res })))
    return
  }
  if (LONG.test(r.url)) e.respondWith(caches.open('ol-v-cdn').then((c) => c.match(r).then((hit) => hit || fetch(r).then((res) => { if (res.ok) c.put(r, res.clone()); return res }))))
})
