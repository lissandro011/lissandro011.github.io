(function () {
  'use strict';

  var VIDEO_ID = 'SsMf6sp0zJc';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- Dibujos ----------

  // Murcielaguito abrazando un corazón
  var CUTE_BAT =
    '<svg viewBox="0 0 120 72" aria-hidden="true" focusable="false">' +
      '<g class="bat-wing bat-wing--l"><path fill="#622638" d="M52 30C42 18 24 12 4 17c6 4 8 10 7 16 7-4 13-2 15 4 6-5 14-3 16 4 4-5 8-5 11-3Z"/></g>' +
      '<g class="bat-wing bat-wing--r"><path fill="#622638" d="M68 30c10-12 28-18 48-13-6 4-8 10-7 16-7-4-13-2-15 4-6-5-14-3-16 4-4-5-8-5-11-3Z"/></g>' +
      '<path fill="#80344a" d="M50 20 47 5l11 10Zm20 0 3-15-11 10Z"/>' +
      '<path fill="#ffa0aa" d="m50.5 14-2-6.5 6 5Zm19 0 2-6.5-6 5Z"/>' +
      '<ellipse cx="60" cy="40" rx="11" ry="13" fill="#80344a"/>' +
      '<circle cx="60" cy="24" r="12" fill="#80344a"/>' +
      '<path d="M52.5 23.5q2.5-3 5 0m5 0q2.5-3 5 0" fill="none" stroke="#fff1f5" stroke-width="1.6" stroke-linecap="round"/>' +
      '<ellipse cx="51" cy="28" rx="2.6" ry="1.6" fill="#ff7d8c" opacity=".85"/>' +
      '<ellipse cx="69" cy="28" rx="2.6" ry="1.6" fill="#ff7d8c" opacity=".85"/>' +
      '<path d="M57.5 29q2.5 2.2 5 0" fill="none" stroke="#fff1f5" stroke-width="1.2" stroke-linecap="round"/>' +
      '<path fill="#fff" d="m58.3 29.6.7 1.8.7-1.5Zm2 .3.7 1.5.7-1.8Z"/>' +
      '<path class="bat-heart" fill="#ff5a72" d="M60 66C47 57 45 47 52 45c4-1 6.5 1 8 3.5 1.5-2.5 4-4.5 8-3.5 7 2 5 12-8 21Z"/>' +
      '<ellipse cx="52.5" cy="47" rx="3" ry="2.4" fill="#80344a"/>' +
      '<ellipse cx="67.5" cy="47" rx="3" ry="2.4" fill="#80344a"/>' +
    '</svg>';

  // Silueta que vuela por el cielo
  var FLYING_BAT =
    '<svg viewBox="0 0 120 50" fill="currentColor" aria-hidden="true" focusable="false">' +
      '<g class="fly-wing fly-wing--l"><path d="M54 22C44 12 26 6 4 10c6 4 8 10 8 16 6-4 12-2 14 4 6-5 14-3 16 4 4-5 9-5 12-3Z"/></g>' +
      '<g class="fly-wing fly-wing--r"><path d="M66 22c10-10 28-16 50-12-6 4-8 10-8 16-6-4-12-2-14 4-6-5-14-3-16 4-4-5-9-5-12-3Z"/></g>' +
      '<path d="m55 14-1-9 4.5 6Zm10 0 1-9-4.5 6Z"/>' +
      '<circle cx="60" cy="16" r="6"/>' +
      '<ellipse cx="60" cy="28" rx="7" ry="10"/>' +
    '</svg>';

  document.querySelectorAll('[data-bat]').forEach(function (el) { el.innerHTML = CUTE_BAT; });
  document.querySelectorAll('[data-flyer]').forEach(function (el) { el.innerHTML = FLYING_BAT; });

  // Estrellas
  var stars = document.getElementById('stars');
  var starCount = window.innerWidth > 700 ? 110 : 70;
  for (var i = 0; i < starCount; i++) {
    var star = document.createElement('span');
    star.className = 'star';
    star.style.left = (Math.random() * 100).toFixed(2) + '%';
    star.style.top = (Math.pow(Math.random(), 1.4) * 75).toFixed(2) + '%';
    star.style.setProperty('--s', (Math.random() * 1.8 + 0.8).toFixed(1) + 'px');
    star.style.setProperty('--d', (Math.random() * 3 + 2.2).toFixed(1) + 's');
    star.style.setProperty('--delay', (-Math.random() * 5).toFixed(1) + 's');
    stars.appendChild(star);
  }

  // Corazones y destellos que suben despacito
  var heartsLayer = document.getElementById('floating-hearts');
  var HEART = '♥︎';
  var FLOAT_COLORS = ['#ff5a72', '#ffb0ba', '#d42a45', '#f6d39b'];

  function spawnFloatingHeart() {
    if (document.hidden || heartsLayer.childElementCount > 16) return;
    var el = document.createElement('span');
    var sparkle = Math.random() < 0.22;
    el.className = 'float-heart';
    el.textContent = sparkle ? '✧' : HEART;
    el.style.setProperty('--x', (Math.random() * 100).toFixed(1) + '%');
    el.style.setProperty('--size', (sparkle ? 10 + Math.random() * 8 : 10 + Math.random() * 14).toFixed(0) + 'px');
    el.style.setProperty('--c', sparkle ? '#f6d39b' : FLOAT_COLORS[Math.floor(Math.random() * 3)]);
    el.style.setProperty('--o', (0.35 + Math.random() * 0.4).toFixed(2));
    el.style.setProperty('--dur', (10 + Math.random() * 8).toFixed(1) + 's');
    el.style.setProperty('--drift', ((Math.random() - 0.5) * 120).toFixed(0) + 'px');
    el.style.setProperty('--rot', ((Math.random() - 0.5) * 80).toFixed(0) + 'deg');
    el.addEventListener('animationend', function () { el.remove(); });
    heartsLayer.appendChild(el);
  }

  if (!reduceMotion) {
    for (var h = 0; h < 4; h++) setTimeout(spawnFloatingHeart, h * 500);
    setInterval(spawnFloatingHeart, 1300);
  }

  // Explosión de corazones (cuando dice que sí, o cuando toca al murcielaguito)
  var burstLayer = document.getElementById('burst');

  function burst(x, y, count, spread) {
    if (reduceMotion) return;
    for (var n = 0; n < count; n++) {
      var el = document.createElement('span');
      var angle = Math.random() * Math.PI * 2;
      var dist = spread * (0.35 + Math.random() * 0.65);
      el.className = 'burst-heart';
      el.textContent = Math.random() < 0.18 ? '✧' : HEART;
      el.style.setProperty('--ox', x + 'px');
      el.style.setProperty('--oy', y + 'px');
      el.style.setProperty('--dx', (Math.cos(angle) * dist).toFixed(0) + 'px');
      el.style.setProperty('--dy', (Math.sin(angle) * dist - spread * 0.25).toFixed(0) + 'px');
      el.style.setProperty('--size', (12 + Math.random() * 20).toFixed(0) + 'px');
      el.style.setProperty('--c', FLOAT_COLORS[Math.floor(Math.random() * FLOAT_COLORS.length)]);
      el.style.setProperty('--rot', ((Math.random() - 0.5) * 120).toFixed(0) + 'deg');
      el.style.setProperty('--dur', (1.2 + Math.random() * 0.9).toFixed(2) + 's');
      el.addEventListener('animationend', function () { this.remove(); });
      burstLayer.appendChild(el);
    }
  }

  function celebrate() {
    var w = window.innerWidth;
    var hgt = window.innerHeight;
    burst(w / 2, hgt * 0.42, 46, Math.min(w, 520) * 0.6);
    setTimeout(function () { burst(w * 0.25, hgt * 0.3, 16, 160); }, 450);
    setTimeout(function () { burst(w * 0.75, hgt * 0.34, 16, 160); }, 800);
  }

  // Tocar al murcielaguito: salta y tira corazoncitos
  document.querySelectorAll('.mascot').forEach(function (mascot) {
    mascot.addEventListener('click', function () {
      var rect = mascot.getBoundingClientRect();
      mascot.classList.remove('is-happy');
      void mascot.offsetWidth;
      mascot.classList.add('is-happy');
      burst(rect.left + rect.width / 2, rect.top + rect.height * 0.6, 10, 90);
      if (navigator.vibrate) navigator.vibrate(15);
    });
    mascot.addEventListener('animationend', function () { mascot.classList.remove('is-happy'); });
  });

  // ---------- Pantallas ----------

  var screens = {};
  document.querySelectorAll('[data-screen]').forEach(function (s) { screens[s.id] = s; });
  var current = 'sorpresa';

  function show(id, push) {
    if (!screens[id] || id === current) return;
    if (current === 'sorpresa') pauseVideo();

    screens[current].hidden = true;
    screens[id].hidden = false;
    current = id;

    window.scrollTo(0, 0);
    if (push !== false) history.pushState({ screen: id }, '', '#' + id);

    var heading = screens[id].querySelector('h1');
    if (heading) heading.focus({ preventScroll: true });

    if (id === 'si') celebrate();
  }

  document.addEventListener('click', function (e) {
    var target = e.target.closest('[data-go]');
    if (target) show(target.getAttribute('data-go'));
  });

  // Siempre empieza por la sorpresa; el botón "atrás" del celu vuelve a la pantalla anterior
  history.replaceState({ screen: 'sorpresa' }, '', location.pathname + location.search);
  window.addEventListener('popstate', function (e) {
    show((e.state && e.state.screen) || 'sorpresa', false);
  });

  // ---------- Video ----------

  var frame = document.getElementById('video-frame');
  var playBtn = document.getElementById('video-play');
  var continueBox = document.getElementById('continue');
  var continueBtn = document.getElementById('btn-continue');
  var iframe = null;
  var player = null;
  var revealTimer = null;

  function revealContinue(delay, focusIt) {
    clearTimeout(revealTimer);
    revealTimer = setTimeout(function () {
      continueBox.classList.add('is-visible');
      if (focusIt) {
        continueBox.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
        continueBtn.classList.remove('is-pulsing');
        void continueBtn.offsetWidth;
        continueBtn.classList.add('is-pulsing');
      }
    }, delay);
  }

  function attachPlayer() {
    if (!iframe || player || !(window.YT && window.YT.Player)) return;
    player = new window.YT.Player(iframe, {
      events: {
        onStateChange: function (e) {
          // Cuando termina el video, la invita a seguir
          if (e.data === window.YT.PlayerState.ENDED) revealContinue(400, true);
        }
      }
    });
  }

  window.onYouTubeIframeAPIReady = attachPlayer;

  playBtn.addEventListener('click', function () {
    var params = 'autoplay=1&playsinline=1&rel=0&enablejsapi=1';
    if (location.protocol.indexOf('http') === 0) params += '&origin=' + encodeURIComponent(location.origin);

    iframe = document.createElement('iframe');
    iframe.src = 'https://www.youtube.com/embed/' + VIDEO_ID + '?' + params;
    iframe.title = 'Nuestro primer beso';
    iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    iframe.allowFullscreen = true;
    frame.replaceChildren(iframe);

    attachPlayer();
    revealContinue(3000);
  });

  document.getElementById('yt-link').addEventListener('click', function () {
    revealContinue(1200);
  });

  // Por si acaso, el botón aparece solo después de un ratito
  setTimeout(function () { revealContinue(0); }, 45000);

  function pauseVideo() {
    if (player && typeof player.pauseVideo === 'function') {
      player.pauseVideo();
    } else if (iframe && iframe.contentWindow) {
      iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'pauseVideo', args: [] }), '*');
    }
  }

  // ---------- La pregunta ----------

  var since = document.getElementById('since');
  var SINCE_KEY = 'lp-novios-desde';

  function readSince() {
    try { return localStorage.getItem(SINCE_KEY); } catch (err) { return null; }
  }

  function paintSince(iso) {
    var date = iso ? new Date(iso) : null;
    if (!date || isNaN(date)) return;
    since.textContent = 'Novios desde el ' + date.toLocaleDateString('es-AR', { day: 'numeric', month: 'long', year: 'numeric' }) + '\u00A0♡';
  }

  paintSince(readSince());

  document.getElementById('btn-si').addEventListener('click', function () {
    var iso = readSince();
    if (!iso) {
      iso = new Date().toISOString();
      try { localStorage.setItem(SINCE_KEY, iso); } catch (err) { /* sin almacenamiento, no pasa nada */ }
    }
    paintSince(iso);
    if (navigator.vibrate) navigator.vibrate([40, 60, 40, 60, 120]);
    show('si');
  });

  var personaBtn = document.getElementById('btn-persona');
  var personaNote = document.getElementById('persona-note');
  personaBtn.addEventListener('click', function () {
    personaBtn.classList.add('is-chosen');
    personaNote.textContent = 'Me encanta la idea. Te espero con un abrazo\u00A0♡';
    var rect = personaBtn.getBoundingClientRect();
    burst(rect.left + rect.width / 2, rect.top + rect.height / 2, 8, 80);
  });
})();
