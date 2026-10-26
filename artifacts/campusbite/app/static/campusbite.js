(() => {
  const offline = document.querySelector('[data-offline-banner]');
  const refreshNetwork = () => {
    if (offline) offline.classList.toggle('is-visible', !navigator.onLine);
  };
  refreshNetwork();
  window.addEventListener('online', refreshNetwork);
  window.addEventListener('offline', refreshNetwork);

  const menu = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-site-nav]');
  if (menu && nav) menu.addEventListener('click', () => {
    const opened = nav.classList.toggle('is-open');
    menu.setAttribute('aria-expanded', String(opened));
  });

  let installEvent;
  const installButton = document.querySelector('[data-install-button]');
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    installEvent = event;
    if (installButton) installButton.hidden = false;
  });
  const installHelp = document.querySelector('[data-install-help]');
  const isAppleMobile = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (installHelp && isAppleMobile && !window.matchMedia('(display-mode: standalone)').matches) {
    installHelp.hidden = false;
  }
  document.querySelectorAll('[data-password-toggle]').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.parentElement?.querySelector('input[type="password"], input[type="text"]');
      if (!input) return;
      const showing = input.type === 'password';
      input.type = showing ? 'text' : 'password';
      button.textContent = showing ? 'Hide' : 'Show';
      button.setAttribute('aria-pressed', String(showing));
    });
  });
  if (installButton) installButton.addEventListener('click', async () => {
    if (!installEvent) return;
    installEvent.prompt();
    await installEvent.userChoice;
    installEvent = null;
    installButton.hidden = true;
  });

  document.querySelectorAll('img[data-fallback]').forEach(image => {
    const revealFallback = () => {
      const fallback = image.parentElement?.querySelector('.photo-fallback');
      if (fallback) fallback.hidden = false;
      image.hidden = true;
    };
    image.addEventListener('error', revealFallback, { once: true });
    if (!image.getAttribute('src')) revealFallback();
  });

  const availabilityRoot = document.querySelector('[data-availability-poll]');
  if (availabilityRoot) {
    const date = availabilityRoot.dataset.date;
    const meal = availabilityRoot.dataset.meal;
    const endpoint = `/api/menu/availability?date=${encodeURIComponent(date)}&meal=${encodeURIComponent(meal)}`;
    const applyAvailability = rows => {
      rows.forEach(row => {
        const id = row.food_id ?? row.id;
        if (id == null) return;
        document.querySelectorAll(`[data-stock-for="${CSS.escape(String(id))}"]`).forEach(node => {
          const quantity = row.stock ?? row.quantity ?? row.available_stock ?? row.stock_count;
          if (quantity != null) node.textContent = String(quantity);
        });
        document.querySelectorAll(`[data-availability-for="${CSS.escape(String(id))}"]`).forEach(node => {
          const quantity = Number(row.stock ?? row.quantity ?? row.available_stock ?? row.stock_count ?? 0);
          const label = row.availability ?? row.stock_status ?? (quantity > 0 ? 'Available' : 'Sold Out');
          node.textContent = label;
          node.classList.toggle('out', quantity <= 0);
          node.classList.toggle('low', row.stock_status === 'Low Stock');
        });
      });
    };
    let pending = false;
    let timer;
    const poll = async () => {
      if (pending || document.hidden) return;
      pending = true;
      try {
        const response = await fetch(endpoint, { headers: { Accept: 'application/json' }, cache: 'no-store' });
        if (!response.ok) throw new Error('Availability could not be refreshed');
        const payload = await response.json();
        applyAvailability(Array.isArray(payload) ? payload : (payload.items || payload.schedules || []));
        const state = document.querySelector('[data-poll-state]');
        if (state) state.textContent = response.headers.get('X-CampusBite-Stale') === '1'
          ? 'Offline — saved stock may be outdated'
          : 'Stock updated just now';
      } catch (_) {
        const state = document.querySelector('[data-poll-state]');
        if (state) state.textContent = 'Offline — saved stock may be outdated';
        if (offline) offline.classList.add('is-visible');
      } finally {
        pending = false;
        timer = window.setTimeout(poll, document.hidden ? 45000 : 20000);
      }
    };
    const onVisibilityChange = () => {
      if (timer) window.clearTimeout(timer);
      if (!document.hidden) poll();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    poll();
  }
})();
