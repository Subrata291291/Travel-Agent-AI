/** Acquire a synchronous lock before React has rendered an updated loading state. */
export function acquireSubmissionLock(lockRef) {
  if (lockRef.current) return false;
  lockRef.current = true;
  return true;
}

/** Keep a response beside the user message whose request produced it. */
export function insertAssistantResponse(messages, userMessageId, assistantMessage) {
  const userIndex = messages.findIndex((message) => message.id === userMessageId);
  if (userIndex < 0) return [...messages, assistantMessage];

  const next = [...messages];
  next.splice(userIndex + 1, 0, assistantMessage);
  return next;
}
