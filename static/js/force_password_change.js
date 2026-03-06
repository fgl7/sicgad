document.addEventListener("DOMContentLoaded", function () {
  var cancelBtn = document.getElementById("force-cancel-btn");
  var logoutForm = document.getElementById("force-logout-form");
  if (!cancelBtn || !logoutForm) return;

  cancelBtn.addEventListener("click", function () {
    logoutForm.submit();
  });
});
