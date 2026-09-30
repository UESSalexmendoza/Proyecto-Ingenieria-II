(() => {
  const element = document.getElementById('mapaDetalleSolicitud');
  if (!element || !window.maplibregl) return;
  const lat = Number(element.dataset.lat), lon = Number(element.dataset.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
  try {
    const map = new maplibregl.Map({container: element, style: 'https://tiles.openfreemap.org/styles/liberty', center: [lon, lat], zoom: 14, interactive: false});
    new maplibregl.Marker({color: '#b7365d'}).setLngLat([lon, lat]).addTo(map);
  } catch (error) { element.textContent = 'Mapa no disponible. Usa la referencia de ubicación indicada arriba.'; }
})();
