// Soru formu: seçenek ekle/çıkar (2-4) ve kapanış zamanını UTC'ye çevir.
(function () {
  "use strict";
  var MIN = 2;
  var rows = Array.prototype.slice.call(document.querySelectorAll(".choice-row-input"));
  var addBtn = document.getElementById("add-choice");
  var form = document.getElementById("question-form");
  if (!form) return;

  // --- Kapanış zamanı ---
  var local = form.querySelector('input[name="closes_at"]');
  var utc = form.querySelector('input[name="closes_at_utc"]');
  function pad(n) { return String(n).padStart(2, "0"); }
  function toLocalInput(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }
  if (local) {
    var existing = local.getAttribute("data-utc");
    if (existing) {            // düzenleme: kayıtlı UTC değerini yerel saate çevirip göster
      var d0 = new Date(existing);
      if (!isNaN(d0)) local.value = toLocalInput(d0);
    }
    if (!local.readOnly) local.min = toLocalInput(new Date(Date.now() + 5 * 60000));
    var sync = function () {
      if (utc && local.value) {
        var d = new Date(local.value);
        utc.value = isNaN(d) ? "" : d.toISOString();
      }
    };
    local.addEventListener("input", sync);
    form.addEventListener("submit", sync);
    sync();
  }

  // --- Seçenekler ---
  if (!rows.length || !addBtn) return;
  var locked = rows[0].querySelector("input").readOnly;
  if (locked) {                // ilk tahminden sonra seçenekler değişmez
    addBtn.hidden = true;
    rows.forEach(function (r) {
      r.querySelector(".remove-choice").hidden = true;
      if (!r.querySelector("input").value.trim()) r.hidden = true;
    });
    return;
  }
  function input(r) { return r.querySelector("input"); }
  function visible() { return rows.filter(function (r) { return !r.hidden; }); }
  function refresh() {
    var n = visible().length;
    addBtn.hidden = n >= rows.length;
    rows.forEach(function (r) { r.querySelector(".remove-choice").hidden = n <= MIN; });
  }
  rows.forEach(function (row, i) {
    var filled = input(row).value.trim() !== "" || row.querySelector(".error");
    row.hidden = i >= MIN && !filled;
    row.querySelector(".remove-choice").addEventListener("click", function () {
      if (visible().length <= MIN) return;
      input(row).value = "";
      row.hidden = true;
      refresh();
    });
  });
  addBtn.addEventListener("click", function () {
    var next = rows.find(function (r) { return r.hidden; });
    if (next) { next.hidden = false; input(next).focus(); }
    refresh();
  });
  refresh();
})();
