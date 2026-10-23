import { h } from "./dom.js";
import { icon } from "./icons.js";

const NAV = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard" },
  { key: "tasks", label: "My Tasks", icon: "tasks" },
  { key: "projects", label: "Projects", icon: "projects" },
  { key: "teams", label: "Teams", icon: "teams" },
  { key: "organizations", label: "Organizations", icon: "org" },
  { key: "notifications", label: "Notifications", icon: "bell", badge: true },
  { key: "reports", label: "Reports", icon: "reports" },
  { key: "activity", label: "Activity Logs", icon: "activity" },
];
const ROLE_LABELS = { admin: "Admin", manager: "Manager", team_lead: "Team Lead", member: "Member" };

let removeHashListener = null;
let shortcutInstalled = false;

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function todayLabel() {
  return new Date().toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });
}

function displayName(me) {
  const full = `${me.first_name || ""} ${me.last_name || ""}`.trim();
  return full || me.email;
}

function initials(me) {
  const first = (me.first_name || "").trim();
  const last = (me.last_name || "").trim();
  if (first || last) return ((first[0] || "") + (last[0] || "")).toUpperCase();
  return me.email.slice(0, 2).toUpperCase();
}

function installSearchShortcut() {
  if (shortcutInstalled) return;
  shortcutInstalled = true;
  document.addEventListener("keydown", (event) => {
    const tag = (event.target.tagName || "").toLowerCase();
    if (event.key !== "/" || ["input", "textarea", "select"].includes(tag)) return;
    const input = document.querySelector(".search input");
    if (input) {
      event.preventDefault();
      input.focus();
    }
  });
}

function pageHead(title, subtitle, withDate) {
  return h("header", { class: "page-head" },
    h("div", {}, h("h1", {}, title), h("p", { class: "muted" }, subtitle)),
    withDate ? h("div", { class: "date-chip" }, icon("calendar", 18), h("span", {}, todayLabel())) : null,
  );
}

function dashboardView(state, org) {
  const name = state.me.first_name || state.me.email.split("@")[0];
  return h("section", {},
    pageHead(`${greeting()}, ${name}! \uD83D\uDC4B`, "Here's what's happening with your projects today.", true),
    h("div", { class: "card" },
      h("h2", {}, "Dashboard widgets"),
      h("p", { class: "muted" },
        `Connected to ${org.name} as ${ROLE_LABELS[org.my_role] || org.my_role}. Stat cards and charts arrive in the next step.`),
    ),
  );
}

function placeholderView(label) {
  return h("section", {},
    pageHead(label, "This page is built in a later step.", false),
    h("div", { class: "card" }, h("p", { class: "muted" }, `${label} is coming soon.`)),
  );
}

function noOrgView(handlers) {
  const input = h("input", { type: "text", placeholder: "Organization name", maxlength: 150, required: true });
  const error = h("p", { class: "form-error", role: "alert" });
  const button = h("button", { type: "submit", class: "btn btn-primary" }, "Create organization");
  const form = h("form", { class: "inline-form" }, input, button);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    button.disabled = true;
    try {
      await handlers.onCreateOrg(input.value.trim());
    } catch (err) {
      error.textContent = (err.data && err.data.name && err.data.name[0]) || err.message;
      button.disabled = false;
    }
  });
  return h("section", {},
    pageHead("Welcome to TaskForge", "Create your first organization to start adding projects and tasks.", false),
    h("div", { class: "card" }, form, error),
  );
}

export function mountShell(root, state, handlers) {
  const { me, orgs, orgId, unread } = state;
  const org = orgs.find((item) => item.id === orgId) || null;
  const main = h("main", { class: "content" });
  const navLinks = new Map();

  const nav = h("nav", { class: "nav" }, NAV.map((item) => {
    const link = h("a", { href: `#/${item.key}` },
      icon(item.icon),
      h("span", {}, item.label),
      item.badge && unread > 0 ? h("span", { class: "badge" }, unread) : null,
    );
    navLinks.set(item.key, link);
    return link;
  }));

  const logoutButton = h("button", { class: "icon-btn", type: "button", title: "Sign out" }, icon("logout", 18));
  logoutButton.addEventListener("click", handlers.onLogout);

  const sidebar = h("aside", { class: "sidebar" },
    h("div", { class: "brand" },
      h("div", { class: "brand-mark" }, "T"),
      h("div", {}, h("div", { class: "brand-name" }, "TaskForge"), h("div", { class: "brand-tag" }, "Plan \u00B7 Assign \u00B7 Achieve")),
    ),
    nav,
    h("div", { class: "sidebar-foot" },
      h("div", { class: "promo" },
        h("strong", {}, "Build better workflows together."),
        h("p", {}, "TaskForge helps teams stay organized, productive and on track."),
      ),
      h("div", { class: "user-card" },
        h("div", { class: "avatar" }, initials(me)),
        h("div", { class: "who" },
          h("div", { class: "name" }, displayName(me)),
          h("div", { class: "role" }, org ? ROLE_LABELS[org.my_role] || org.my_role : "No organization"),
        ),
        logoutButton,
      ),
    ),
  );

  const select = h("select", { class: "org-select", "aria-label": "Switch organization" },
    orgs.map((item) => h("option", { value: item.id, selected: item.id === orgId }, item.name)));
  select.addEventListener("change", () => handlers.onSwitchOrg(Number(select.value)));

  const orgSwitch = h("div", { class: "org-switch" },
    h("div", { class: "org-avatar" }, org ? org.name[0].toUpperCase() : "?"),
    h("div", {}, h("div", { class: "org-name" }, org ? org.name : "No organization"), h("div", { class: "org-sub" }, "Organization")),
    h("span", { class: "chev" }, icon("chevron", 18)),
    orgs.length ? select : null,
  );

  const topbar = h("header", { class: "topbar" },
    h("div", { class: "search" },
      icon("search", 18),
      h("input", { type: "text", placeholder: "Search projects, tasks, or people...", "aria-label": "Search" }),
      h("kbd", {}, "/"),
    ),
    h("div", { class: "topbar-right" },
      h("a", { class: "icon-btn", href: "#/notifications", title: "Notifications" },
        icon("bell", 20),
        unread > 0 ? h("span", { class: "bell-badge" }, unread) : null,
      ),
      h("button", { class: "icon-btn", type: "button", disabled: true, title: "Light theme comes later" }, icon("sun", 20)),
      orgSwitch,
    ),
  );

  const footer = h("footer", { class: "footer" },
    h("span", {}, "TaskForge v1.0.0"),
    h("a", { href: "/api/docs/", target: "_blank", rel: "noopener" }, "API Docs"),
  );

  function routeKey() {
    const key = location.hash.replace(/^#\//, "");
    return NAV.some((item) => item.key === key) ? key : "dashboard";
  }

  function renderRoute() {
    const key = routeKey();
    navLinks.forEach((link, linkKey) => link.classList.toggle("active", linkKey === key));
    let view;
    if (!org) view = noOrgView(handlers);
    else if (key === "dashboard") view = dashboardView(state, org);
    else view = placeholderView(NAV.find((item) => item.key === key).label);
    main.replaceChildren(view);
  }

  if (removeHashListener) removeHashListener();
  window.addEventListener("hashchange", renderRoute);
  removeHashListener = () => window.removeEventListener("hashchange", renderRoute);
  installSearchShortcut();

  root.replaceChildren(h("div", { class: "app" }, sidebar, h("div", { class: "main" }, topbar, main, footer)));
  renderRoute();
}
