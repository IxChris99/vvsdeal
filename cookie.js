/* cookie.js — letvægts samtykke-banner (GDPR/ePrivacy).
   VVSdeal bruger kun NØDVENDIGE cookies/localStorage (din kurv) og ingen sporing.
   Banneret indlæses på alle sider via <script src="/cookie.js" defer></script>. */
(function () {
  var KEY = "vvsdeal_cookie_samtykke";
  try { if (localStorage.getItem(KEY)) return; } catch (e) { return; }

  var css = ''
    + '#cookiebar{position:fixed;left:0;right:0;bottom:0;z-index:9998;'
    + 'background:#0e3a5c;color:#eaf2f8;padding:16px 20px;'
    + 'box-shadow:0 -6px 24px rgba(0,0,0,.25);font-family:"Segoe UI",system-ui,sans-serif;'
    + 'font-size:.92rem;line-height:1.5}'
    + '#cookiebar .cb-inner{max-width:1100px;margin:0 auto;display:flex;gap:18px;'
    + 'align-items:center;flex-wrap:wrap;justify-content:space-between}'
    + '#cookiebar p{margin:0;flex:1;min-width:240px}'
    + '#cookiebar a{color:#ff7a1a;text-decoration:underline;font-weight:600}'
    + '#cookiebar .cb-btns{display:flex;gap:10px;flex-wrap:wrap}'
    + '#cookiebar button{border:none;border-radius:999px;padding:10px 22px;'
    + 'font-weight:700;font-size:.9rem;cursor:pointer;font-family:inherit}'
    + '#cookiebar .cb-ok{background:#ff7a1a;color:#fff}'
    + '#cookiebar .cb-min{background:transparent;color:#eaf2f8;border:1.5px solid rgba(255,255,255,.5)}'
    + '@media(max-width:600px){#cookiebar .cb-inner{justify-content:center;text-align:center}}';

  var html = ''
    + '<div class="cb-inner">'
    + '<p>🍪 Vi bruger kun <b>nødvendige cookies</b> for at få din kurv til at virke — '
    + 'vi sporer dig ikke og deler ikke dine data. '
    + '<a href="/persondatapolitik.html">Læs persondatapolitik</a></p>'
    + '<div class="cb-btns">'
    + '<button class="cb-min" data-valg="noedvendige">Kun nødvendige</button>'
    + '<button class="cb-ok" data-valg="alle">OK, forstået</button>'
    + '</div></div>';

  function vis() {
    var style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
    var bar = document.createElement("div");
    bar.id = "cookiebar";
    bar.innerHTML = html;
    document.body.appendChild(bar);
    bar.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      try { localStorage.setItem(KEY, b.dataset.valg); } catch (e) {}
      bar.remove();
    });
  }

  if (document.body) vis();
  else document.addEventListener("DOMContentLoaded", vis);
})();
