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
    input, button { font: inherit; padding: .7rem; }
    input { width: min(34rem, 70%); }
    button { background: #b8562f; color: white; border: 0; border-radius: 8px; cursor: pointer; }
    #cases, #calendar { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 1rem; }
    .warning { color: #873813; font-weight: 650; }
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
  <h2>Expedientes</h2>
  <section id="cases" aria-live="polite"></section>
</main>
<script>
const statusNode = document.querySelector('#status');
document.querySelector('#load').addEventListener('click', async () => {
  const token = document.querySelector('#token').value;
  statusNode.textContent = 'Cargando…';
  const headers = {Authorization: `Bearer ${token}`};
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
});
</script>
</body>
</html>"""
