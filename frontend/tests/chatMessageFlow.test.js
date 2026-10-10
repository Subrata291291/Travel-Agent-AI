import test from "node:test";
import assert from "node:assert/strict";

import {
  acquireSubmissionLock,
  insertAssistantResponse,
} from "../src/services/chatMessageFlow.js";


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
