export function getOrCreateSessionId(storage) {
  try {
    const sessionStorage = storage ?? globalThis.sessionStorage;
    const key = "travel_agent_session_id";
    const existing = sessionStorage.getItem(key);
    if (existing) return existing;
    const newSession = `web-${crypto.randomUUID()}`;
    sessionStorage.setItem(key, newSession);
    return newSession;
  } catch {
    return `web-${crypto.randomUUID()}`;
  }
}

export function createNewSessionId(storage) {
  const newSession = `web-${crypto.randomUUID()}`;
  try {
    const sessionStorage = storage ?? globalThis.sessionStorage;
    sessionStorage.setItem("travel_agent_session_id", newSession);
  } catch {
    // The in-memory session still works when browser storage is unavailable.
  }
  return newSession;
}

export function chatRequestPayload(message, sessionId) {
  return { message, session_id: sessionId };
}
