// Navigation does not depend on WebGL, data loading or the live API.
const tabs = [...document.querySelectorAll('.tab')];
const views = [...document.querySelectorAll('.view')];
const names = new Map(views.map((view) => [view.id.replace('-view', ''), view.id]));

function showView(viewId, { updateHash = true, focus = false } = {}) {
  if (!views.some((view) => view.id === viewId)) return;
  for (const view of views) view.hidden = view.id !== viewId;
  for (const tab of tabs) {
    const active = tab.getAttribute('aria-controls') === viewId;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
  }
  if (updateHash) history.pushState(null, '', `#${viewId.replace('-view', '')}`);
  if (focus) {
    const view = document.getElementById(viewId);
    view.tabIndex = -1;
    view.focus({ preventScroll: true });
  }
  window.scrollTo({ top: 0, behavior: 'instant' });
  dispatchEvent(new CustomEvent('viewchange', { detail: { viewId } }));
}

window.showView = showView;
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => showView(tab.getAttribute('aria-controls')));
  tab.addEventListener('keydown', (event) => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    tabs[next].focus();
    tabs[next].scrollIntoView({ block: 'nearest', inline: 'nearest' });
    showView(tabs[next].getAttribute('aria-controls'));
  });
});
document.addEventListener('click', (event) => {
  const link = event.target.closest('[data-view]');
  if (link) showView(link.dataset.view, { focus: true });
});
const readHash = () => {
  if (location.hash === '#main-content') return; // Let the skip link focus the current workspace.
  showView(names.get(location.hash.slice(1)) || 'overview-view', { updateHash: false });
};
addEventListener('popstate', readHash);
addEventListener('hashchange', readHash);
readHash();

const guide = document.getElementById('reading-guide');
document.getElementById('help-open').addEventListener('click', () => guide.showModal());
document.getElementById('help-close').addEventListener('click', () => guide.close());
guide.addEventListener('click', (event) => {
  const bounds = guide.getBoundingClientRect();
  if (event.target === guide && (event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom)) guide.close();
});

// Keep charts available even if the machine cannot create a 3D/WebGL context.
import('./app.js').catch(async (error) => {
  const loading = document.getElementById('loading');
  if (loading) {
    loading.textContent = 'The 3D scene could not start. Enable hardware acceleration or try another browser. The calculator, agent examples and results remain available.';
  }
  for (const id of ['inspect-example', 'next-event', 'camera-reset', 'reset', 'f-source', 'f-altitude', 'f-dilution', 'f-pc', 'f-miss', 'f-censored', 'f-null']) {
    document.getElementById(id).disabled = true;
  }
  try {
    const [{ renderCharts }, summaryResponse, eventsResponse] = await Promise.all([
      import('./charts.js'), fetch('./data/summary.json'), fetch('./data/events.json'),
    ]);
    if (!summaryResponse.ok || !eventsResponse.ok) throw new Error('Static dataset unavailable');
    const summary = await summaryResponse.json();
    const events = await eventsResponse.json();
    document.getElementById('pop-n').textContent = summary.population.events.toLocaleString();
    document.getElementById('samp-n').textContent = events.length.toLocaleString();
    document.getElementById('charts').replaceChildren();
    renderCharts(document.getElementById('charts'), summary, events);
  } catch {
    document.getElementById('charts').textContent = 'The distribution files could not be loaded. Serve the frontend folder over HTTP and check that data/events.json and data/summary.json are present.';
  }
  console.warn('3D workspace unavailable:', error.message);
});
