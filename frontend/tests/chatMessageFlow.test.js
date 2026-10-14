import test from "node:test";
import assert from "node:assert/strict";

import {
  acquireSubmissionLock,
  insertAssistantResponse,
} from "../src/services/chatMessageFlow.js";
import {
  chatRequestPayload,
  createNewSessionId,
  getOrCreateSessionId,
} from "../src/services/chatSession.js";


test("one synchronous submission window starts only one workflow request", () => {
  const lock = { current: false };
  let workflowCalls = 0;

  if (acquireSubmissionLock(lock)) workflowCalls += 1;
  if (acquireSubmissionLock(lock)) workflowCalls += 1;

  assert.equal(workflowCalls, 1);
  lock.current = false;
  assert.equal(acquireSubmissionLock(lock), true);
});


test("overlapping responses stay attached to their initiating messages", () => {
  const transcript = [
    { id: "user-1", role: "user", content: "first" },
    { id: "user-2", role: "user", content: "second" },
  ];
  const withSecondResponse = insertAssistantResponse(
    transcript,
    "user-2",
    { id: "assistant-2", role: "assistant", content: "second answer" },
  );
  const complete = insertAssistantResponse(
    withSecondResponse,
    "user-1",
    { id: "assistant-1", role: "assistant", content: "first answer" },
  );

  assert.deepEqual(complete.map(({ id }) => id), [
    "user-1", "assistant-1", "user-2", "assistant-2",
  ]);
});


test("chat turns reuse the session stored for the open tab", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const firstSession = getOrCreateSessionId(storage);
  const nextTurnSession = getOrCreateSessionId(storage);

  assert.equal(nextTurnSession, firstSession);
  assert.deepEqual(chatRequestPayload("25th", nextTurnSession), {
    message: "25th",
    session_id: firstSession,
  });
});


test("a new session gets a distinct workflow key", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const oldSession = getOrCreateSessionId(storage);
  const newSession = createNewSessionId(storage);

  assert.notEqual(newSession, oldSession);
  assert.equal(getOrCreateSessionId(storage), newSession);
  assert.notEqual(
    chatRequestPayload("Plan a trip to Sikkim", newSession).session_id,
    oldSession,
  );
});
