(() => {
  const element = document.getElementById('mapaVoluntarioPanel') || document.getElementById('mapaVoluntarioDetalle');
  if (!element || !window.maplibregl) return;
  const lat = Number(element.dataset.lat), lon = Number(element.dataset.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
  let points = [];
  try {
    const raw = JSON.parse(document.getElementById('puntosVoluntario').textContent);
    points = Array.isArray(raw) ? raw : [raw];
  } catch (_) { /* La lista mantiene el acceso a las solicitudes. */ }
  try {
    const map = new maplibregl.Map({container: element, style: 'https://tiles.openfreemap.org/styles/liberty', center: [lon, lat], zoom: 11});
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    new maplibregl.Marker({color: '#17365d'}).setLngLat([lon, lat]).setPopup(new maplibregl.Popup().setText('Mi zona aproximada')).addTo(map);
    for (const point of points) {
      if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) continue;
      const wrap = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = point.tipo;
      const info = document.createElement('p'); info.textContent = `${point.km} km · zona aproximada`;
      const link = document.createElement('a'); link.textContent = 'Ver detalle';
      link.href = `${element.dataset.detailPrefix || "/panel/voluntario/ayudas/"}${encodeURIComponent(point.url)}/`;
      wrap.append(title, info, link);
      new maplibregl.Marker({color: '#b7365d'}).setLngLat([point.lon, point.lat])
        .setPopup(new maplibregl.Popup().setDOMContent(wrap)).addTo(map);
    }
  } catch (_) { element.textContent = 'Mapa no disponible. Consulta la lista de solicitudes cercanas.'; }
})();
