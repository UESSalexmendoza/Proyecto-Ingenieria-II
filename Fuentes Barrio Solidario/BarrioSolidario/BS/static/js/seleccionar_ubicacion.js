(function () {
  'use strict';
  const contenedor = document.querySelector('[data-location-picker]');
  if (!contenedor) return;
  const lat = document.getElementById(contenedor.dataset.latId);
  const lon = document.getElementById(contenedor.dataset.lonId);
  const mensaje = document.getElementById(contenedor.dataset.statusId);
  const boton = document.getElementById(contenedor.dataset.useId);
  function anunciar(texto) { if (mensaje) mensaje.textContent = texto; }
  if (!lat || !lon) {
    anunciar('No se encontraron los campos de coordenadas. Recarga la página.');
    return;
  }
  if (typeof maplibregl === 'undefined') {
    anunciar('No se descargó la librería del mapa. Verifica la conexión o el bloqueo de cdn.jsdelivr.net y recarga la página. Puedes ingresar las coordenadas manualmente.');
    return;
  }
  if (typeof maplibregl.supported === 'function' && !maplibregl.supported()) {
    anunciar('Este navegador no tiene WebGL disponible para mostrar el mapa. Puedes ingresar las coordenadas manualmente.');
    return;
  }
  const inicialLat = Number(lat.value);
  const inicialLon = Number(lon.value);
  const tienePunto = lat.value !== '' && lon.value !== '' && Number.isFinite(inicialLat) && Number.isFinite(inicialLon)
    && Math.abs(inicialLat) <= 90 && Math.abs(inicialLon) <= 180;
  let mapa;
  try {
    mapa = new maplibregl.Map({
      container: contenedor,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: tienePunto ? [inicialLon, inicialLat] : [-79.922359, -2.170998],
      zoom: tienePunto ? 15 : 12
    });
  } catch (error) {
    anunciar('No se pudo iniciar el mapa: ' + (error.message || 'error del navegador') + '. Puedes ingresar las coordenadas manualmente.');
    return;
  }
  mapa.addControl(new maplibregl.NavigationControl({showCompass: false}), 'top-left');
  let marcador;
  function actualizar(latitude, longitude, mover) {
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
      anunciar('Las coordenadas están fuera de rango.');
      return;
    }
    lat.value = latitude.toFixed(6);
    lon.value = longitude.toFixed(6);
    if (marcador) marcador.setLngLat([longitude, latitude]);
    else {
      marcador = new maplibregl.Marker({draggable: true}).setLngLat([longitude, latitude]).addTo(mapa);
      marcador.on('dragend', function () {
        const posicion = marcador.getLngLat();
        actualizar(posicion.lat, posicion.lng, false);
      });
    }
    if (mover) mapa.flyTo({center: [longitude, latitude], zoom: 15});
    anunciar('Punto seleccionado. Latitud ' + lat.value + ', longitud ' + lon.value + '.');
  }
  mapa.on('click', function (evento) { actualizar(evento.lngLat.lat, evento.lngLat.lng, false); });
  mapa.on('error', function (evento) {
    const detalle = evento && evento.error && evento.error.message ? evento.error.message : 'no se pudieron descargar los datos';
    anunciar('Error al cargar el fondo del mapa: ' + detalle + '. Comprueba el acceso a tiles.openfreemap.org. Puedes ingresar las coordenadas manualmente.');
  });
  if (tienePunto) actualizar(inicialLat, inicialLon, false);
  function actualizarCampos() {
    if (lat.value && lon.value) actualizar(Number(lat.value), Number(lon.value), true);
  }
  lat.addEventListener('change', actualizarCampos);
  lon.addEventListener('change', actualizarCampos);
  if (boton) boton.addEventListener('click', function () {
    if (!navigator.geolocation) { anunciar('Tu navegador no permite obtener la ubicación. Selecciona un punto o escribe las coordenadas.'); return; }
    anunciar('Solicitando permiso de ubicación al navegador…');
    navigator.geolocation.getCurrentPosition(
      function (pos) { actualizar(pos.coords.latitude, pos.coords.longitude, true); },
      function () { anunciar('No se pudo obtener tu ubicación. Selecciona un punto o escribe las coordenadas.'); },
      {enableHighAccuracy: false, timeout: 12000, maximumAge: 60000}
    );
  });
  setTimeout(function () { mapa.resize(); }, 150);
})();
