const REFRESH_KEY = "tf_refresh";
let accessToken = null;
let refreshing = null;

export class ApiError extends Error {
  constructor(status, data) {
    super(data && typeof data.detail === "string" ? data.detail : `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

export const hasSession = () => Boolean(localStorage.getItem(REFRESH_KEY));

export function logout() {
  accessToken = null;
  localStorage.removeItem(REFRESH_KEY);
}

async function parse(response) {
  if (response.status === 204) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function send(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  return fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// One refresh at a time, even if several requests get a 401 together.
export function restoreSession() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const data = await response.json();
        accessToken = data.access;
        if (data.refresh) localStorage.setItem(REFRESH_KEY, data.refresh);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request(path, options = {}) {
  let response = await send(path, options);
  if (response.status === 401 && options.auth !== false) {
    if (await restoreSession()) {
      response = await send(path, options);
    } else {
      logout();
      window.dispatchEvent(new Event("tf:logout"));
    }
  }
  const data = await parse(response);
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body: body ?? {} }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};

export async function login(email, password) {
  const data = await request("/api/auth/login/", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
  accessToken = data.access;
  localStorage.setItem(REFRESH_KEY, data.refresh);
}
