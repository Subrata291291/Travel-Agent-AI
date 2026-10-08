import api from "./api";

/**
 * Send a message to the Travel Agent.
 *
 * The backend owns:
 * - authentication
 * - tenant isolation
 * - perception
 * - planning
 * - tool execution
 * - booking logic
 * - cancellation logic
 */
export async function sendChatMessage({
  message,
  sessionId,
}) {
  const response = await api.post("/chat", {
    message,
    session_id: sessionId,
  });

  return response.data;
}