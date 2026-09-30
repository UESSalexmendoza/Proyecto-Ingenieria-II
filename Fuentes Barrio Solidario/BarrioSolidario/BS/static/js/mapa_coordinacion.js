(() => {
  const element = document.getElementById('mapaCoordinacion');
  const data = document.getElementById('puntosCoordinacion');
  if (!element || !data) return;
  const puntos = JSON.parse(data.textContent);
  if (!puntos.length) { element.textContent = 'No hay solicitudes con ubicación autorizada en este momento.'; return; }
  if (!window.maplibregl) { element.textContent = 'Mapa no disponible. Usa la bandeja de solicitudes.'; return; }
  try {
    const mapa = new maplibregl.Map({container: element, style: 'https://tiles.openfreemap.org/styles/liberty', center: [puntos[0].lon, puntos[0].lat], zoom: 10});
    mapa.addControl(new maplibregl.NavigationControl(), 'top-right');
    for (const p of puntos) {
      const caja = document.createElement('div');
      const titulo = document.createElement('strong'); titulo.textContent = `${p.codigo} · ${p.tipo}`;
      const enlace = document.createElement('a'); enlace.href = p.url; enlace.textContent = 'Revisar solicitud';
      caja.append(titulo, document.createElement('br'), enlace);
      new maplibregl.Marker({color: '#b7365d'}).setLngLat([p.lon, p.lat])
        .setPopup(new maplibregl.Popup().setDOMContent(caja)).addTo(mapa);
    }
  } catch (_) { element.textContent = 'Mapa no disponible. Usa la bandeja de solicitudes.'; }
})();
