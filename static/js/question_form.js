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
  var dateEl = document.getElementById("closes_date");
  var hourEl = document.getElementById("closes_hour");
  var minEl = document.getElementById("closes_minute");
  var errEl = document.getElementById("closing-error");
  if (local && dateEl && hourEl && minEl) {
    for (var h = 0; h < 24; h++) hourEl.add(new Option(pad(h), pad(h)));
    for (var m = 0; m < 60; m += 5) minEl.add(new Option(pad(m), pad(m)));
    var locked = dateEl.readOnly;
    var existing = local.getAttribute("data-utc");
    var initial = "";
    if (existing) {            // düzenleme: kayıtlı UTC değerini yerel saate çevirip göster
      var d0 = new Date(existing);
      if (!isNaN(d0)) initial = toLocalInput(d0);
    } else if (local.value) {
      initial = local.value;   // hatalı gönderimden dönen değer
    }
    if (initial.indexOf("T") > 0) {
      var tm = initial.split("T")[1];
      dateEl.value = initial.split("T")[0];
      hourEl.value = tm.slice(0, 2);
      var mm = tm.slice(3, 5);
      if (!Array.prototype.some.call(minEl.options, function (o) { return o.value === mm; })) {
        minEl.add(new Option(mm, mm));   // 5 dakika dışındaki kayıtlı değer
      }
      minEl.value = mm;
    }
    if (!locked) dateEl.min = toLocalInput(new Date(Date.now() + 5 * 60000)).split("T")[0];
    var complete = function () { return !!(dateEl.value && hourEl.value && minEl.value); };
    var sync = function () {
      if (complete()) {
        local.value = dateEl.value + "T" + hourEl.value + ":" + minEl.value;
        var d = new Date(local.value);
        if (utc) utc.value = isNaN(d) ? "" : d.toISOString();
        if (errEl) errEl.hidden = true;
      } else {
        local.value = "";
        if (utc) utc.value = "";
      }
    };
    [dateEl, hourEl, minEl].forEach(function (el) {
      el.addEventListener("input", sync);
      el.addEventListener("change", sync);
    });
    // Yakalama aşamasında çalışır: eksikse gönderimi durdurur ve "Kaydediliyor" durumunu engeller.
    form.addEventListener("submit", function (e) {
      sync();
      if (!locked && !complete()) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (errEl) { errEl.hidden = false; errEl.scrollIntoView({ block: "center" }); }
      }
    }, true);
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
