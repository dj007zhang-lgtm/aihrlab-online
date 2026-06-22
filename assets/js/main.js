/* AIHR数智引擎 — 交互脚本 */

// ---- GA4 event helper ----
function trackEvent(eventName, params) {
  if (typeof gtag !== 'undefined') {
    gtag('event', eventName, params);
  }
}
// ---- / GA4 event helper ----

document.addEventListener('DOMContentLoaded', () => {
  // Mobile nav toggle
  const navToggle = document.querySelector('.nav-toggle');
  const siteNav = document.querySelector('.site-nav');
  if (navToggle && siteNav) {
    navToggle.addEventListener('click', () => {
      siteNav.classList.toggle('open');
    });
    // Close nav on link click
    siteNav.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        siteNav.classList.remove('open');
      });
    });
  }

  // Highlight current page in nav
  const currentPath = window.location.pathname;
  siteNav?.querySelectorAll('a').forEach(link => {
    const href = link.getAttribute('href');
    if (href && href !== '/' && currentPath.includes(href.replace(/\/$/, ''))) {
      link.classList.add('active');
    }
    if (href === '/' && (currentPath === '/' || currentPath.endsWith('index.html'))) {
      link.classList.add('active');
    }
  });

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // --- QR Code Modal System ---
  initGateModal();
  initGateButtons();
  initGateExposureTracking();
});

/* Create and manage QR code modal */
function initGateModal() {
  // Check if modal already exists
  if (document.getElementById('qr-gate-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'qr-gate-modal';
  overlay.className = 'qr-modal-overlay';
  overlay.innerHTML = `
    <div class="qr-modal">
      <button class="modal-close" aria-label="关闭">&times;</button>
      <h3 id="qr-modal-title">扫码解锁完整内容</h3>
      <img src="/assets/images/wechat-qrcode.jpg" alt="AIHR数智引擎公众号二维码" id="qr-modal-img" width="180" height="180">
      <p class="modal-instruction" id="qr-modal-instruction">
        微信扫一扫，关注「AIHR数智引擎」
      </p>
    </div>
  `;
  document.body.appendChild(overlay);

  // Close on overlay click
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeGateModal();
  });

  // Close on button click
  overlay.querySelector('.modal-close').addEventListener('click', closeGateModal);

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeGateModal();
  });
}

function closeGateModal() {
  const modal = document.getElementById('qr-gate-modal');
  if (modal) modal.classList.remove('show');
}

function openGateModal(config) {
  const modal = document.getElementById('qr-gate-modal');
  if (!modal) return;

  const title = modal.querySelector('#qr-modal-title');
  const instruction = modal.querySelector('#qr-modal-instruction');

  if (config && config.title) title.textContent = config.title;
  else title.textContent = '扫码解锁完整内容';

  if (config && config.instruction) instruction.innerHTML = config.instruction;
  else instruction.textContent = '微信扫一扫，关注「AIHR数智引擎」';

  modal.classList.add('show');

  // Track modal open
  const gateId = config && config.gateId ? config.gateId : 'unknown';
  trackEvent('qr_modal_open', {
    gate_id: gateId,
    page_path: window.location.pathname
  });
}

/* Bind all gate buttons */
function initGateButtons() {
  document.querySelectorAll('.btn-gate, .gate-trigger').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const title = btn.getAttribute('data-gate-title') || '扫码解锁完整内容';
      const instruction = btn.getAttribute('data-gate-instruction') || '微信扫一扫，关注「AIHR数智引擎」公众号，回复关键词获取完整资源。';
      const gateId = btn.getAttribute('data-gate-id') || btn.closest('.gate-card, .asset-card')?.querySelector('h3')?.textContent || 'unknown';

      // Track gate button click
      trackEvent('gate_click', {
        gate_id: gateId,
        page_path: window.location.pathname.toString(),
        gate_type: btn.closest('.asset-card') ? 'asset_download' : 'content_unlock'
      });

      openGateModal({ title, instruction, gateId });
    });
  });
}

/* Track gate card exposure via IntersectionObserver */
function initGateExposureTracking() {
  const tracked = new Set();

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !tracked.has(entry.target)) {
        tracked.add(entry.target);
        const gateCard = entry.target.closest('.gate-card, .asset-card');
        const gateId = gateCard?.querySelector('h3')?.textContent || 'unknown';
        const gateType = entry.target.closest('.asset-card') ? 'asset_card' : 'content_gate';

        trackEvent('gate_view', {
          gate_id: gateId,
          gate_type: gateType,
          page_path: window.location.pathname.toString()
        });
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.gate-card, .asset-card').forEach(el => observer.observe(el));
}
