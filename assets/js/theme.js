/* Securade.ai theme runtime — dark mode toggle, mobile nav, scroll reveals, scroll-top */
(function () {
  'use strict';

  /* ---------- Theme (light / dark / system) ---------- */
  var STORAGE_KEY = 'securade-theme';
  var root = document.documentElement;

  function applyTheme(theme) {
    if (theme === 'light' || theme === 'dark') {
      root.setAttribute('data-theme', theme);
    } else {
      root.removeAttribute('data-theme');
    }
  }

  function getStoredTheme() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  function setStoredTheme(theme) {
    try {
      if (theme) localStorage.setItem(STORAGE_KEY, theme);
      else localStorage.removeItem(STORAGE_KEY);
    } catch (e) { /* ignore */ }
  }

  // Apply stored or system preference on load
  applyTheme(getStoredTheme());
  // Mark <html> so CSS can opt-in to JS-only animations.
  root.classList.add('js-enabled');

  function currentTheme() {
    var stored = getStoredTheme();
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function toggleTheme() {
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    setStoredTheme(next);
    applyTheme(next);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (btn) {
      e.preventDefault();
      toggleTheme();
    }
  });

  // React to OS preference changes when user has no explicit choice
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    var handle = function () {
      if (!getStoredTheme()) applyTheme(null);
    };
    if (mq.addEventListener) mq.addEventListener('change', handle);
    else if (mq.addListener) mq.addListener(handle);
  }

  /* ---------- Mobile nav ---------- */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.navbar-toggler');
    if (btn) {
      e.preventDefault();
      var targetId = btn.getAttribute('data-target') || btn.getAttribute('aria-controls');
      var menu = targetId ? document.getElementById(targetId) : document.querySelector('.navbar-collapse');
      if (!menu) return;
      var isOpen = menu.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      return;
    }
    // Close menu when a nav link is clicked
    var link = e.target.closest('.navbar-collapse a');
    if (link) {
      var openMenu = document.querySelector('.navbar-collapse.is-open');
      if (openMenu) {
        openMenu.classList.remove('is-open');
        var t = document.querySelector('.navbar-toggler');
        if (t) t.setAttribute('aria-expanded', 'false');
      }
    }
  });

  /* ---------- Sticky-header scroll state ---------- */
  var header = document.querySelector('.site-header, .header');
  var scrollTop = document.querySelector('.scroll-top');
  function updateScrollState() {
    var y = window.scrollY || window.pageYOffset;
    if (header) header.classList.toggle('is-scrolled', y > 8);
    if (scrollTop) scrollTop.classList.toggle('is-visible', y > 400);
  }
  updateScrollState();
  window.addEventListener('scroll', updateScrollState, { passive: true });

  if (scrollTop) {
    scrollTop.addEventListener('click', function (e) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ---------- Reveal-on-scroll (respects prefers-reduced-motion) ---------- */
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var revealEls = document.querySelectorAll('.reveal');
  if (!reduce && 'IntersectionObserver' in window && revealEls.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.05 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  }

  /* ---------- Resources page: category filter ---------- */
  var chipContainer = document.querySelector('[data-filter-chips]');
  var postGrid = document.querySelector('[data-post-grid]');
  if (chipContainer && postGrid) {
    chipContainer.addEventListener('click', function (e) {
      var chip = e.target.closest('.filter-chip');
      if (!chip) return;
      var cat = chip.getAttribute('data-category') || 'all';
      chipContainer.querySelectorAll('.filter-chip').forEach(function (c) {
        c.classList.toggle('is-active', c === chip);
      });
      postGrid.querySelectorAll('[data-category]').forEach(function (card) {
        if (cat === 'all' || card.getAttribute('data-category') === cat) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  }
  // Lazy-start the hero video after first paint: the poster image acts as LCP,
  // then we kick off the video so users still see motion.
  var heroVideo = document.querySelector('.hero-image .hero-video');
  if (heroVideo) {
    var heroImage = heroVideo.closest('.hero-image');
    var startVideo = function () {
      heroVideo.load();
      heroVideo.play().catch(function () { /* autoplay blocked; poster stays */ });
      heroVideo.addEventListener('playing', function () {
        if (heroImage) heroImage.classList.add('has-video');
      }, { once: true });
    };
    if ('requestIdleCallback' in window) {
      requestIdleCallback(startVideo, { timeout: 2000 });
    } else {
      setTimeout(startVideo, 600);
    }
  }
})();
