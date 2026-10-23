import { api, ApiError, hasSession, login, logout, restoreSession } from "./api.js";
import { h } from "./dom.js";
import { mountShell } from "./shell.js";

const ORG_KEY = "tf_org";
const root = document.getElementById("root");

function describeError(err) {
  if (err instanceof ApiError && err.status === 401) return "Invalid email or password.";
  if (err instanceof ApiError) return err.message;
  if (err instanceof TypeError) return "Cannot reach the server. Is it running?";
  return "Something went wrong. Please try again.";
}

function showLogin(notice = "") {
  const error = h("p", { class: "form-error", role: "alert" }, notice);
  const email = h("input", { type: "email", required: true, autocomplete: "username", placeholder: "you@example.com" });
  const password = h("input", { type: "password", required: true, autocomplete: "current-password", placeholder: "Your password" });
  const submit = h("button", { type: "submit", class: "btn btn-primary" }, "Sign in");
  const form = h("form", { class: "login-form" },
    h("label", {}, "Email", email),
    h("label", {}, "Password", password),
    error,
    submit,
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    submit.disabled = true;
    try {
      await login(email.value.trim(), password.value);
      await showApp();
    } catch (err) {
      error.textContent = describeError(err);
      submit.disabled = false;
    }
  });
  root.replaceChildren(
    h("div", { class: "login" },
      h("div", { class: "login-card" },
        h("div", { class: "brand" },
          h("div", { class: "brand-mark" }, "T"),
          h("div", {}, h("div", { class: "brand-name" }, "TaskForge"), h("div", { class: "brand-tag" }, "Plan \u00B7 Assign \u00B7 Achieve")),
        ),
        form,
      ),
    ),
  );
  email.focus();
}

async function loadState() {
  const [me, orgPage, unreadData] = await Promise.all([
    api.get("/api/auth/me/"),
    api.get("/api/organizations/"),
    api.get("/api/notifications/unread-count/").catch(() => ({ unread: 0 })),
  ]);
  const orgs = orgPage.results;
  const saved = Number(localStorage.getItem(ORG_KEY));
  const current = orgs.find((org) => org.id === saved) || orgs[0] || null;
  return { me, orgs, orgId: current ? current.id : null, unread: unreadData.unread };
}

function mount(state) {
  mountShell(root, state, {
    onLogout: () => {
      logout();
      showLogin();
    },
    onSwitchOrg: (orgId) => {
      localStorage.setItem(ORG_KEY, String(orgId));
      mount({ ...state, orgId });
    },
    onCreateOrg: async (name) => {
      await api.post("/api/organizations/", { name });
      await showApp();
    },
  });
}

async function showApp() {
  mount(await loadState());
}

window.addEventListener("tf:logout", () => showLogin("Your session expired. Please sign in again."));

(async function boot() {
  if (hasSession() && (await restoreSession())) {
    try {
      await showApp();
      return;
    } catch (err) {
      showLogin(describeError(err));
      return;
    }
  }
  showLogin();
})();
