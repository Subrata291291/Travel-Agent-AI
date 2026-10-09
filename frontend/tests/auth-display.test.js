import assert from "node:assert/strict";
import test from "node:test";

import { attachBearerToken } from "../src/services/authHeaders.js";
import {
  clearAuthToken,
  readAuthToken,
  storeAuthToken,
} from "../src/services/authStorage.js";
import {
  getUserDisplayName,
  getUserInitial,
} from "../src/utils/userDisplay.js";

test("dashboard display uses the user's name and never their ID", () => {
  const user = {
    name: "  Ada Lovelace  ",
    email: "ada@example.com",
    user_id: "user-123",
  };

  assert.equal(getUserDisplayName(user), "Ada Lovelace");
  assert.equal(getUserInitial(user), "A");
});

test("dashboard display falls back to email, then a generic label", () => {
  assert.equal(
    getUserDisplayName({ user_id: "user-123", email: "ada@example.com" }),
    "ada@example.com",
  );
  assert.equal(getUserDisplayName({ user_id: "user-123" }), "Traveller");
});

test("auth token is persisted, read for requests, and cleared on logout", () => {
  const values = new Map();
  const previousStorage = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };

  try {
    storeAuthToken("test-token");
    assert.equal(readAuthToken(), "test-token");
    assert.equal(
      attachBearerToken({ headers: {} }, readAuthToken()).headers.Authorization,
      "Bearer test-token",
    );
    clearAuthToken();
    assert.equal(readAuthToken(), null);
  } finally {
    if (previousStorage === undefined) {
      delete globalThis.localStorage;
    } else {
      globalThis.localStorage = previousStorage;
    }
  }
});
