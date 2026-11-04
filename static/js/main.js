// Bildirim kutularını birkaç saniye sonra yumuşakça kaldır.
(function () {
  document.querySelectorAll(".message").forEach(function (el) {
    setTimeout(function () {
      el.classList.add("is-hiding");
      setTimeout(function () { el.remove(); }, 450);
    }, 5000);
  });
})();
