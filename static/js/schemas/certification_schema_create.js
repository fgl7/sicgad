document.addEventListener("DOMContentLoaded", function () {
  const select = document.querySelector('select[name="source_dataset"]');
  if (!select) return;

  select.addEventListener("change", function () {
    const value = this.value;
    const url = new URL(window.location.href);
    if (value) {
      url.searchParams.set("source_dataset", value);
    } else {
      url.searchParams.delete("source_dataset");
    }
    window.location.href = url.toString();
  });
});
