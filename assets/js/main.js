/* AIHR数智引擎 — 数据埋点 + A/B Test 框架 */

// ============ GA4 事件辅助 ============
function trackEvent(name, params = {}) {
  if (typeof gtag !== 'undefined') {
    gtag('event', name, {
      ...params,
      send_to: 'G-BWLGRVRRGN'
    });
  }
}

// ============ 滚动深度埋点 ============
(function initScrollTracking() {
  const milestones = [25, 50, 75, 90, 100];
  const fired = new Set();
  let maxDepth = 0;

  function getScrollPct() {
    const h = document.documentElement;
    const scrollTop = window.scrollY || h.scrollTop;
    const scrollHeight = h.scrollHeight - h.clientHeight;
    if (scrollHeight <= 0) return 0;
    return Math.round((scrollTop / scrollHeight) * 100);
  }

  function checkScroll() {
    const pct = getScrollPct();
    if (pct > maxDepth) maxDepth = pct;
    for (const m of milestones) {
      if (pct >= m && !fired.has(m)) {
        fired.add(m);
        trackEvent('scroll_depth', {
          percent: m,
          page_path: window.location.pathname,
          page_title: document.title
        });
      }
    }
  }

  // 用 IntersectionObserver 监听文章正文底部（更精准）
  function initArticleBottomTracking() {
    const bottom = document.querySelector('.article-qrcode, .article-body');
    if (!bottom) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !fired.has('article_end')) {
          fired.add('article_end');
          trackEvent('article_end_view', {
            page_path: window.location.pathname,
            max_scroll_depth: maxDepth
          });
        }
      });
    }, { threshold: 0.3 });

    observer.observe(bottom);
  }

  window.addEventListener('scroll', throttle(checkScroll, 500), { passive: true });
  window.addEventListener('load', () => {
    checkScroll();
    initArticleBottomTracking();
  });

  // 页面离开时发送最大深度
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      trackEvent('page_engagement', {
        page_path: window.location.pathname,
        max_scroll_depth: maxDepth,
        engaged_time_sec: Math.round((Date.now() - loadTime) / 1000)
      });
    }
  });
})();

// ============ 停留时长埋点 ============
const loadTime = Date.now();
let engagedSeconds = 0;
let engagementTimer = null;

function startEngagementTimer() {
  if (engagementTimer) return;
  engagementTimer = setInterval(() => {
    engagedSeconds++;
    // 每 30 秒打点一次，避免高频
    if (engagedSeconds % 30 === 0) {
      trackEvent('engagement_ping', {
        page_path: window.location.pathname,
        engaged_seconds: engagedSeconds
      });
    }
  }, 1000);
}

function stopEngagementTimer() {
  clearInterval(engagementTimer);
  engagementTimer = null;
}

// 页面可见时计时
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    startEngagementTimer();
  } else {
    stopEngagementTimer();
    trackEvent('engagement_pause', {
      page_path: window.location.pathname,
      total_engaged_seconds: engagedSeconds
    });
  }
});

window.addEventListener('load', startEngagementTimer);
window.addEventListener('beforeunload', () => {
  stopEngagementTimer();
  trackEvent('page_exit', {
    page_path: window.location.pathname,
    total_engaged_seconds: engagedSeconds,
    max_scroll_depth: Math.round(
      (window.scrollY / (document.documentElement.scrollHeight - document.documentElement.clientHeight)) * 100
    ) || 0
  });
});

// ============ 二维码区域埋点 ============
function initQRCTATracking() {
  // 文章页二维码区域
  const qrSection = document.querySelector('.article-qrcode');
  if (qrSection) {
    // 曝光追踪
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          trackEvent('qr_code_view', {
            page_path: window.location.pathname,
            cta_variant: localStorage.getItem('qr_cta_variant') || 'A'
          });
          observer.disconnect();
        }
      });
    }, { threshold: 0.5 });
    observer.observe(qrSection);

    // 点击二维码图片
    const qrImg = qrSection.querySelector('img');
    if (qrImg) {
      qrImg.style.cursor = 'pointer';
      qrImg.addEventListener('click', () => {
        trackEvent('qr_code_click', {
          page_path: window.location.pathname,
          cta_variant: localStorage.getItem('qr_cta_variant') || 'A'
        });
      });
    }
  }

  // 首页订阅区二维码
  const followSection = document.getElementById('follow');
  if (followSection) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          trackEvent('follow_section_view', { page_path: window.location.pathname });
          observer.disconnect();
        }
      });
    }, { threshold: 0.3 });
    observer.observe(followSection);
  }
}

// ============ A/B Test 框架 ============
const ABTests = {
  // 测试：文章页二维码 CTA 文案
  qr_cta: {
    name: 'qr_cta',
    variants: [
      {
        id: 'A',
        // 当前版本
        cta: '这篇文章的分析框架，会在公众号持续更新。',
        hint: '关注后回复 <code>关键词</code> 获取配套工具'
      },
      {
        id: 'B',
        // 测试版本：更直接的价值承诺
        cta: '同类深度分析，公众号每周更新。',
        hint: '关注后回复 <code>关键词</code> 获取文章配套工具'
      }
    ],
    getVariant() {
      let stored = localStorage.getItem('ab_qr_cta');
      if (stored) return JSON.parse(stored);
      const variant = this.variants[Math.random() < 0.5 ? 0 : 1];
      localStorage.setItem('ab_qr_cta', JSON.stringify(variant));
      return variant;
    },
    apply() {
      const v = this.getVariant();
      localStorage.setItem('qr_cta_variant', v.id);
      const qrSection = document.querySelector('.article-qrcode');
      if (qrSection) {
        const ctaP = qrSection.querySelector('p:first-child');
        const hintP = qrSection.querySelector('.qr-hint');
        if (ctaP) ctaP.innerHTML = v.cta;
        if (hintP) hintP.innerHTML = v.hint;
      }
      // 发送 A/B 曝光事件
      trackEvent('ab_test_exposure', {
        test_name: 'qr_cta',
        variant: v.id,
        page_path: window.location.pathname
      });
    }
  }
};

// ============ 文章卡片点击埋点 ============
function initArticleCardTracking() {
  document.querySelectorAll('.article-card a[href]').forEach(card => {
    card.addEventListener('click', (e) => {
      const articleCard = card.closest('.article-card');
      const title = articleCard?.querySelector('h3')?.textContent || '';
      trackEvent('article_card_click', {
        article_title: title,
        page_path: window.location.pathname,
        link_url: card.href || card.getAttribute('href')
      });
    });
  });
}

// ============ 工具函数 ============
function throttle(fn, wait) {
  let last = 0;
  return function(...args) {
    const now = Date.now();
    if (now - last >= wait) {
      last = now;
      fn.apply(this, args);
    }
  };
}

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', () => {
  // Mobile nav
  const navToggle = document.querySelector('.nav-toggle');
  const siteNav = document.querySelector('.site-nav');
  if (navToggle && siteNav) {
    navToggle.addEventListener('click', () => {
      siteNav.classList.toggle('open');
    });
    siteNav.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => siteNav.classList.remove('open'));
    });
  }

  // Highlight current page
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

  // Smooth scroll
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // --- 埋点初始化 ---
  initQRCTATracking();
  initArticleCardTracking();

  // --- A/B Test 应用（仅文章页）---
  if (document.querySelector('.article-qrcode')) {
    ABTests.qr_cta.apply();
  }

  // 首次访问标记
  if (!localStorage.getItem('returning_visitor')) {
    trackEvent('first_visit', { page_path: window.location.pathname });
    localStorage.setItem('returning_visitor', 'true');
  }


  // --- 资源库门控弹窗 ---
  (function() {
    var overlay = document.createElement('div');
    overlay.className = 'gate-overlay';
    overlay.id = 'gate-overlay';
    overlay.innerHTML = '<div class="gate-modal">' +
      '<div class="gate-modal-header">' +
        '<h3 id="gate-title">获取资源</h3>' +
        '<p>关注公众号「AIHR数智引擎」，回复关键词获取下载链接</p>' +
      '</div>' +
      '<div class="gate-modal-body">' +
        '<div class="gate-qrcode-wrap">' +
          '<img src="/assets/images/qrcode-wechat.jpg" alt="关注公众号">' +
        '</div>' +
        '<p class="gate-instruction" id="gate-instruction"></p>' +
      '</div>' +
      '<div class="gate-modal-footer">' +
        '<button class="gate-close-btn" id="gate-close">我知道了</button>' +
      '</div>' +
    '</div>';
    document.body.appendChild(overlay);

    var closeBtn = document.getElementById('gate-close');
    function closeModal() { overlay.classList.remove('open'); }
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) closeModal();
    });
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closeModal();
    });

    document.querySelectorAll('.gate-trigger').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var title = this.dataset.gateTitle || '获取资源';
        var instruction = this.dataset.gateInstruction || '';
        document.getElementById('gate-title').textContent = title;
        var instEl = document.getElementById('gate-instruction');
        if (instEl) instEl.innerHTML = instruction;
        overlay.classList.add('open');
        if (typeof trackEvent === 'function') {
          trackEvent('gate_open', { resource_name: title, page_path: window.location.pathname });
        }
      });
    });
  })();
});



// ============ 全局门控弹窗函数 ============
(function() {
  var overlay = null;

  function createOverlay() {
    overlay = document.createElement('div');
    overlay.className = 'gate-overlay';
    overlay.id = 'gate-overlay';
    overlay.innerHTML = '<div class="gate-modal">' +
      '<div class="gate-modal-header">' +
        '<h3 id="gate-title">获取资源</h3>' +
        '<p>关注公众号「AIHR数智引擎」，回复关键词获取下载链接</p>' +
      '</div>' +
      '<div class="gate-modal-body">' +
        '<div class="gate-qrcode-wrap">' +
          '<img src="/assets/images/qrcode-wechat.jpg" alt="关注公众号 AIHR数智引擎">' +
        '</div>' +
        '<p class="gate-instruction" id="gate-instruction"></p>' +
      '</div>' +
      '<div class="gate-modal-footer">' +
        '<button class="gate-close-btn" id="gate-close">我知道了</button>' +
      '</div>' +
    '</div>';
    document.body.appendChild(overlay);

    var closeBtn = document.getElementById('gate-close');
    function closeModal() { overlay.classList.remove('open'); }
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) closeModal();
    });
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closeModal();
    });
  }

  // openGate: 接受按钮元素，读取 data 属性
  window.openGate = function(btn) {
    if (!overlay) createOverlay();
    var title = (btn && btn.dataset && btn.dataset.gateTitle) ? btn.dataset.gateTitle : '获取资源';
    var instruction = (btn && btn.dataset && btn.dataset.gateInstruction) ? btn.dataset.gateInstruction : '';
    var titleEl = document.getElementById('gate-title');
    var instEl = document.getElementById('gate-instruction');
    if (titleEl) titleEl.textContent = title;
    if (instEl) instEl.innerHTML = instruction;
    overlay.classList.add('open');
    if (typeof trackEvent === 'function') {
      trackEvent('gate_open', { resource_name: title, page_path: window.location.pathname });
    }
  };
})();
