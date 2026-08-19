DASHBOARD_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Expediente PR</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #f4f1e8; color: #17211b; }
    header { background: #123b2d; color: white; padding: 1.2rem 5vw; }
    main { max-width: 1100px; margin: auto; padding: 2rem 5vw; }
    .auth, article { background: white; border: 1px solid #d7d2c5; border-radius: 12px; padding: 1rem; }
    input, button, select { font: inherit; padding: .7rem; }
    input { width: min(34rem, 70%); }
    button { background: #b8562f; color: white; border: 0; border-radius: 8px; cursor: pointer; }
    #cases, #calendar { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 1rem; }
    .warning { color: #873813; font-weight: 650; }
    .actions { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }
    .muted { color: #5d655f; }
    .connected { color: #14613f; font-weight: 700; }
  </style>
</head>
<body>
<header><h1>Expediente PR</h1><p>Gestión jurídica auditable para Puerto Rico</p></header>
<main>
  <p class="warning">Entorno de desarrollo: no utilice información real ni confidencial.</p>
  <section class="auth">
    <label for="token">Token de acceso</label><br>
    <input id="token" type="password" autocomplete="off" placeholder="exp_…">
    <button id="load">Cargar expedientes</button>
    <p id="status" role="status"></p>
  </section>
  <h2>Próximos eventos</h2>
  <section id="calendar" aria-live="polite"></section>
  <h2>Integraciones</h2>
  <section id="integrations" aria-live="polite">
    <article>
      <h3>Google Workspace</h3>
      <p id="google-state" class="muted">Cargue el panel para comprobar la conexión.</p>
      <div class="actions">
        <button id="connect-google" type="button">Conectar Google</button>
        <select id="google-calendar" hidden aria-label="Calendario de Google"></select>
        <button id="save-calendar" type="button" hidden>Usar este calendario</button>
        <button id="watch-calendar" type="button" hidden>Activar sincronización</button>
        <button id="disconnect-google" type="button" hidden>Desconectar</button>
      </div>
    </article>
    <article>
      <h3>WhatsApp Business</h3>
      <p id="whatsapp-state" class="muted">Requiere una cuenta de WhatsApp Business Platform.</p>
      <div class="actions">
        <button id="connect-whatsapp" type="button">Comenzar conexión</button>
        <button id="disconnect-whatsapp" type="button" hidden>Desconectar</button>
      </div>
    </article>
  </section>
  <h2>Expedientes</h2>
  <section id="cases" aria-live="polite"></section>
</main>
<script>
const statusNode = document.querySelector('#status');
let activeHeaders = null;
async function disconnectProvider(provider) {
  const response = await fetch(`/integrations/${provider}`, {
    method: 'DELETE', headers: activeHeaders
  });
  if (!response.ok) { statusNode.textContent = 'No fue posible desconectar la cuenta.'; return; }
  await loadIntegrations();
}
async function startAuthorization(provider) {
  if (!activeHeaders) { statusNode.textContent = 'Primero cargue el panel con su token.'; return; }
  const endpoint = provider === 'google'
    ? '/integrations/google/authorize' : '/integrations/whatsapp/signup';
  const response = await fetch(endpoint, {headers: activeHeaders});
  if (!response.ok) { statusNode.textContent = 'La integración no está configurada en el servidor.'; return; }
  const result = await response.json();
  window.location.assign(result.url);
}
async function loadIntegrations() {
  const response = await fetch('/integrations', {headers: activeHeaders});
  if (!response.ok) return;
  const connections = await response.json();
  const google = connections.find(item => item.provider === 'google');
  const whatsapp = connections.find(item => item.provider === 'whatsapp');
  const googleState = document.querySelector('#google-state');
  const whatsappState = document.querySelector('#whatsapp-state');
  document.querySelector('#disconnect-google').hidden = !google;
  document.querySelector('#disconnect-whatsapp').hidden = !whatsapp;
  googleState.textContent = google
    ? `Conectado · calendario: ${google.configuration.calendar_id || 'primary'}`
    : 'No conectado.';
  googleState.className = google ? 'connected' : 'muted';
  whatsappState.textContent = whatsapp
    ? 'WhatsApp Business conectado.' : 'No conectado.';
  whatsappState.className = whatsapp ? 'connected' : 'muted';
  const selector = document.querySelector('#google-calendar');
  const save = document.querySelector('#save-calendar');
  const watch = document.querySelector('#watch-calendar');
  selector.hidden = !google; save.hidden = !google; watch.hidden = !google;
  if (google) {
    const calendars = await fetch('/integrations/google/calendars', {headers: activeHeaders});
    if (calendars.ok) {
      const choices = await calendars.json();
      selector.replaceChildren(...choices.map(item => {
        const option = document.createElement('option');
        option.value = item.id; option.textContent = item.summary;
        option.selected = item.id === google.configuration.calendar_id;
        return option;
      }));
    }
  }
}
document.querySelector('#connect-google').addEventListener(
  'click', () => startAuthorization('google')
);
document.querySelector('#connect-whatsapp').addEventListener(
  'click', () => startAuthorization('whatsapp')
);
document.querySelector('#disconnect-google').addEventListener(
  'click', () => disconnectProvider('google')
);
document.querySelector('#disconnect-whatsapp').addEventListener(
  'click', () => disconnectProvider('whatsapp')
);
document.querySelector('#save-calendar').addEventListener('click', async () => {
  const calendarId = document.querySelector('#google-calendar').value;
  const response = await fetch('/integrations/google/calendar', {
    method: 'PUT',
    headers: {...activeHeaders, 'Content-Type': 'application/json'},
    body: JSON.stringify({calendar_id: calendarId})
  });
  statusNode.textContent = response.ok
    ? 'Calendario seleccionado.' : 'No fue posible seleccionar el calendario.';
  if (response.ok) await loadIntegrations();
});
document.querySelector('#watch-calendar').addEventListener('click', async () => {
  const response = await fetch('/integrations/google/calendar/watch', {
    method: 'POST', headers: activeHeaders
  });
  statusNode.textContent = response.ok
    ? 'Sincronización de Google Calendar activada.'
    : 'No fue posible activar la sincronización; revise el webhook HTTPS.';
});
document.querySelector('#load').addEventListener('click', async () => {
  const token = document.querySelector('#token').value;
  statusNode.textContent = 'Cargando…';
  const headers = {Authorization: `Bearer ${token}`};
  activeHeaders = headers;
  const start = new Date(); const end = new Date(start.getTime() + 90 * 86400000);
  const [caseResponse, eventResponse] = await Promise.all([
    fetch('/cases', {headers}),
    fetch(`/calendar/events?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`, {headers})
  ]);
  if (!caseResponse.ok || !eventResponse.ok) { statusNode.textContent = 'No fue posible autenticar o cargar el panel.'; return; }
  const cases = await caseResponse.json(); const events = await eventResponse.json();
  document.querySelector('#cases').replaceChildren(...cases.map(item => {
    const card = document.createElement('article');
    const title = document.createElement('h2'); title.textContent = item.case_number;
    const name = document.createElement('p'); name.textContent = item.title;
    const forum = document.createElement('p'); forum.textContent = `${item.forum} · ${item.status}`;
    card.append(title, name, forum); return card;
  }));
  document.querySelector('#calendar').replaceChildren(...events.map(item => {
    const card = document.createElement('article');
    const title = document.createElement('h3'); title.textContent = item.title;
    const when = document.createElement('p'); when.textContent = new Date(item.starts_at).toLocaleString('es-PR');
    const state = document.createElement('p'); state.textContent = `${item.event_type} · ${item.status}`;
    card.append(title, when, state); return card;
  }));
  statusNode.textContent = `${cases.length} expediente(s) y ${events.length} evento(s). El token no se guardó.`;
  await loadIntegrations();
});
</script>
</body>
</html>"""
