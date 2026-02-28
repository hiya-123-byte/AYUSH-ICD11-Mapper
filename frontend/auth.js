/* =====================================================
   Auth Logic for AYUSH–ICD-11 PoC
   - Signup / Signin
   - localStorage based (PoC)
   - Toast notifications
   - Password show / hide
   ===================================================== */


/* ---------- TOAST NOTIFICATION ---------- */
function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerText = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("show");
  }, 100);

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}


/* ---------- SIGN UP ---------- */
function signup() {
  const username = document.getElementById("su-user").value.trim();
  const password = document.getElementById("su-pass").value.trim();

  if (!username || !password) {
    showToast("Please fill all fields");
    return;
  }

  const userData = {
    username: username,
    password: password
  };

  localStorage.setItem("ayushUser", JSON.stringify(userData));

  showToast("Account created successfully");

  setTimeout(() => {
    window.location.href = "index.html";
  }, 1200);
}


/* ---------- SIGN IN ---------- */
function signin() {
  const username = document.getElementById("si-user").value.trim();
  const password = document.getElementById("si-pass").value.trim();

  const savedUser = JSON.parse(localStorage.getItem("ayushUser"));

  if (!savedUser) {
    showToast("No account found. Please sign up first");
    return;
  }

  if (
    username === savedUser.username &&
    password === savedUser.password
  ) {
    localStorage.setItem("loggedIn", "true");
    showToast("Logged in successfully");

    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 1200);
  } else {
    showToast("Invalid username or password");
  }
}


/* ---------- AUTH CHECK (Protect Dashboard) ---------- */
function checkAuth() {
  const isLoggedIn = localStorage.getItem("loggedIn");

  if (isLoggedIn !== "true") {
    window.location.href = "index.html";
  }
}


/* ---------- LOGOUT ---------- */
function logout() {
  localStorage.removeItem("loggedIn");
  showToast("Logged out");

  setTimeout(() => {
    window.location.href = "index.html";
  }, 800);
}


/* ---------- PASSWORD SHOW / HIDE ---------- */
function togglePassword(inputId, icon) {
  const input = document.getElementById(inputId);

  if (input.type === "password") {
    input.type = "text";
    icon.textContent = "🙈";
  } else {
    input.type = "password";
    icon.textContent = "👁";
  }
}
