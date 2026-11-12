/* Anki 卡组生成器 · 页面增强
   原则：所有内容在无 JS 时也完整可读；这里只加便利功能。 */
(function () {
  'use strict';

  /* ---------- 顶栏滚动阴影 ---------- */
  var masthead = document.querySelector('.masthead');
  if (masthead) {
    var syncStuck = function () {
      masthead.classList.toggle('is-stuck', window.scrollY > 8);
    };
    syncStuck();
    window.addEventListener('scroll', syncStuck, { passive: true });
  }

  /* ---------- 复制命令 ---------- */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy') ? resolve() : reject(new Error('copy failed'));
      } catch (err) {
        reject(err);
      }
      document.body.removeChild(ta);
    });
  }

  document.querySelectorAll('.copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = document.getElementById(btn.dataset.copyTarget || '');
      if (!target) return;
      var label = btn.textContent;
      copyText(target.textContent).then(function () {
        btn.textContent = '已复制';
        btn.classList.add('is-done');
        setTimeout(function () {
          btn.textContent = label;
          btn.classList.remove('is-done');
        }, 1600);
      }).catch(function () {
        btn.textContent = '复制失败';
        setTimeout(function () { btn.textContent = label; }, 1600);
      });
    });
  });

  /* ---------- 流程页签 ---------- */
  document.querySelectorAll('[data-tabs]').forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;
    var panels = tabs.map(function (tab) {
      return document.getElementById(tab.getAttribute('aria-controls'));
    });

    function activate(index, moveFocus) {
      tabs.forEach(function (tab, i) {
        var on = i === index;
        tab.classList.toggle('is-active', on);
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
        tab.tabIndex = on ? 0 : -1;
        if (panels[i]) panels[i].hidden = !on;
      });
      if (moveFocus) tabs[index].focus();
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { activate(i, false); });
      tab.addEventListener('keydown', function (event) {
        var key = event.key;
        if (['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'Home', 'End'].indexOf(key) === -1) return;
        event.preventDefault();
        var next =
          key === 'Home' ? 0 :
          key === 'End' ? tabs.length - 1 :
          (i + (key === 'ArrowRight' || key === 'ArrowDown' ? 1 : -1) + tabs.length) % tabs.length;
        activate(next, true);
      });
    });

    // 无 JS 时两个面板都完整展开；脚本就绪后才收成页签
    activate(0, false);
  });

  /* ---------- 流程图放大 ---------- */
  var dialog = document.getElementById('lightbox');
  if (dialog && typeof dialog.showModal === 'function') {
    var dialogImg = dialog.querySelector('img');
    var closeBtn = dialog.querySelector('.lightbox-close');
    var lastTrigger = null;

    document.querySelectorAll('[data-zoom]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        lastTrigger = btn;
        var source = btn.querySelector('img');
        dialogImg.src = btn.dataset.zoom;
        dialogImg.alt = source ? source.alt : '';
        dialog.showModal();
      });
    });

    closeBtn.addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener('close', function () {
      dialogImg.removeAttribute('src');
      if (lastTrigger) lastTrigger.focus();
    });
  }

  /* ---------- plan.json 着色 ---------- */
  var jsonBlock = document.getElementById('trace-code');
  if (jsonBlock) {
    var source = jsonBlock.textContent
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    jsonBlock.innerHTML = source.replace(
      /("(?:[^"\\]|\\.)*")(\s*:)?/g,
      function (match, str, colon) {
        return colon
          ? '<span class="k">' + str + '</span>' + colon
          : '<span class="s">' + str + '</span>';
      }
    );
  }

  /* ---------- 导航当前项 ---------- */
  var navLinks = Array.prototype.slice.call(
    document.querySelectorAll('.nav a[href^="#"]')
  );
  if (navLinks.length && 'IntersectionObserver' in window) {
    var linkById = {};
    navLinks.forEach(function (link) {
      linkById[link.getAttribute('href').slice(1)] = link;
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var active = linkById[entry.target.id];
        if (!active) return;
        navLinks.forEach(function (link) { link.classList.remove('is-current'); });
        active.classList.add('is-current');
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

    Object.keys(linkById).forEach(function (id) {
      var section = document.getElementById(id);
      if (section) observer.observe(section);
    });
  }
})();
