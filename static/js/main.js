// Tahmince genel betikleri: yerel saat, geri sayım, bildirimler, gönderim durumu.
(function () {
  "use strict";

  // Bildirimler birkaç saniye sonra kaybolur (hatalar ekranda kalır).
  document.querySelectorAll(".message:not(.message-error)").forEach(function (el) {
    setTimeout(function () {
      el.classList.add("is-hiding");
      setTimeout(function () { el.remove(); }, 450);
    }, 5000);
  });

  // Tarihler sunucuda UTC saklanır; burada kullanıcının yerel saatine çevrilir.
  var fmt = new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium", timeStyle: "short" });
  document.querySelectorAll("time[data-local]").forEach(function (el) {
    var d = new Date(el.getAttribute("datetime"));
    if (!isNaN(d)) el.textContent = fmt.format(d);
  });

  // Kalan süre geri sayımı.
  function remaining(ms) {
    var s = Math.floor(ms / 1000);
    var d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + " gün " + h + " sa";
    if (h > 0) return h + " sa " + m + " dk";
    if (m > 0) return m + " dk " + (s % 60) + " sn";
    return (s % 60) + " sn";
  }
  var counters = document.querySelectorAll("[data-countdown]");
  function tick() {
    var now = Date.now();
    counters.forEach(function (el) {
      var end = new Date(el.getAttribute("data-countdown")).getTime();
      if (isNaN(end)) return;
      var left = end - now;
      if (left <= 0) {
        el.textContent = "Süre doldu";
        el.classList.add("is-ended");
      } else {
        el.textContent = remaining(left);
      }
    });
    // Tahmin sayfası açıkken süre dolarsa sayfayı yenile ki tahmin düğmeleri kapansın.
    var page = document.querySelector("[data-reload-at]");
    if (page && Date.parse(page.getAttribute("data-reload-at")) <= now) {
      page.removeAttribute("data-reload-at");
      setTimeout(function () { window.location.reload(); }, 1200);
    }
  }
  if (counters.length || document.querySelector("[data-reload-at]")) {
    tick();
    setInterval(tick, 1000);
  }

  // Gönderim sırasında düğmeyi kilitle ve "yükleniyor" durumunu göster (çift tıklamayı da önler).
  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (btn) {
        var text = btn.getAttribute("data-loading-text");
        if (text) btn.textContent = text;
        btn.setAttribute("aria-busy", "true");
        btn.classList.add("btn");
      });
    });
  });
})();
