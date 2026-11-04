// Seçenek ekle/çıkar. JS kapalıysa 5 alan da görünür kalır; doğrulama sunucuda yapılır.
(function () {
  var MIN = 2;
  var rows = Array.prototype.slice.call(document.querySelectorAll(".option-row"));
  var addBtn = document.getElementById("add-option");
  if (!rows.length || !addBtn) return;

  function input(row) { return row.querySelector("input"); }
  function visible() { return rows.filter(function (r) { return !r.hidden; }); }

  function refresh() {
    var count = visible().length;
    addBtn.hidden = count >= rows.length;
    rows.forEach(function (row) {
      row.querySelector(".remove-option").hidden = count <= MIN;
    });
  }

  rows.forEach(function (row, i) {
    var hasContent = input(row).value.trim() !== "" || row.querySelector(".error");
    row.hidden = i >= MIN && !hasContent;
    row.querySelector(".remove-option").addEventListener("click", function () {
      if (visible().length <= MIN) return;
      input(row).value = "";
      row.hidden = true;
      refresh();
    });
  });

  addBtn.addEventListener("click", function () {
    var next = rows.find(function (r) { return r.hidden; });
    if (next) {
      next.hidden = false;
      input(next).focus();
    }
    refresh();
  });

  refresh();
})();
