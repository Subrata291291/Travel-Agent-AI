const TOKEN_KEY = "travel_agent_token";

export function readAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function storeAuthToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}
