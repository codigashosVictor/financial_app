const CACHE = "finance-v1";

// ── Instalación ──────────────────────────────────────────────
self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(clients.claim());
});

// ── Notificaciones push ──────────────────────────────────────
self.addEventListener("push", (e) => {
  if (!e.data) return;

  const data = e.data.json();

  const options = {
    body: data.body || "",
    icon: "/static/img/icon-192.png",
    badge: "/static/img/icon-192.png",
    tag: data.tag || "finance-alert",
    data: { url: data.url || "/" },
    actions: data.actions || [],
    requireInteraction: data.urgent || false,
    vibrate: data.urgent ? [200, 100, 200] : [100],
  };

  e.waitUntil(
    self.registration.showNotification(data.title || "Finance App", options),
  );
});

// ── Click en notificación ────────────────────────────────────
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = e.notification.data?.url || "/";

  e.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // Si la app ya está abierta, enfocarla
        for (const client of clientList) {
          if (client.url.includes(self.location.origin)) {
            client.focus();
            client.navigate(url);
            return;
          }
        }
        // Si no, abrirla
        return clients.openWindow(url);
      }),
  );
});
