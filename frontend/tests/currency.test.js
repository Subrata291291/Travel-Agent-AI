import test from "node:test";
import assert from "node:assert/strict";

import {
  formatCurrency,
  getInrRate,
  getInrPriceDisplay,
  parseCurrencyPriceLine,
} from "../src/utils/currency.js";

const referenceQuote = { rate: 100, date: "2026-10-13" };

test("EUR source amounts use the same dated INR display model in each view", () => {
  const transportOptionTotal = getInrPriceDisplay(328.05, "EUR", referenceQuote);
  const chatConfirmationTotal = getInrPriceDisplay(328.05, "EUR", referenceQuote);
  const myTripsTotal = getInrPriceDisplay(328.05, "EUR", referenceQuote);

  assert.equal(transportOptionTotal.primary, "₹32,805.00");
  assert.equal(chatConfirmationTotal.primary, transportOptionTotal.primary);
  assert.equal(myTripsTotal.primary, transportOptionTotal.primary);
  assert.equal(
    myTripsTotal.secondary,
    "Approx. €328.05 · reference rate dated 2026-10-13",
  );
});

test("per-traveller and total source amounts convert independently once", () => {
  const originalPerTraveller = 65.61;
  const originalTotal = 328.05;
  const perTravellerDisplay = getInrPriceDisplay(
    originalPerTraveller, "EUR", referenceQuote,
  );
  const totalDisplay = getInrPriceDisplay(originalTotal, "EUR", referenceQuote);

  assert.equal(perTravellerDisplay.primary, "₹6,561.00");
  assert.equal(totalDisplay.primary, "₹32,805.00");
  assert.equal(originalPerTraveller, 65.61);
  assert.equal(originalTotal, 328.05);
});

test("INR values are displayed directly even if a foreign exchange quote is supplied", () => {
  assert.equal(getInrPriceDisplay(34976.69, "INR", referenceQuote).primary, "₹34,976.69");
});

test("missing and invalid quotes show the original currency without fabricating INR", () => {
  const missing = getInrPriceDisplay(328.05, "EUR", null, true);
  const invalid = getInrPriceDisplay(328.05, "EUR", { rate: 0, date: "2026-10-13" }, true);

  for (const display of [missing, invalid]) {
    assert.equal(display.primary, "€328.05");
    assert.equal(display.converted, false);
    assert.equal(display.secondary, "INR conversion unavailable; showing provider currency");
  }
});

test("a pending quote does not briefly show a foreign amount as the primary price", () => {
  const display = getInrPriceDisplay(328.05, "EUR");
  assert.equal(display.primary, "Loading INR conversion…");
  assert.equal(display.secondary, "Supplier price: €328.05");
});

test("Frankfurter quotes are validated and retain the provider reference date", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl;
  globalThis.fetch = async (url) => {
    requestedUrl = String(url);
    return {
      ok: true,
      json: async () => ({ rate: 101.25, date: "2026-10-12" }),
    };
  };
  try {
    const quote = await getInrRate("CHF");
    assert.match(requestedUrl, /CHF\/INR$/);
    assert.deepEqual(quote, { rate: 101.25, date: "2026-10-12" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("currency formatting is locale-aware and consistently rounded to two decimals", () => {
  assert.equal(formatCurrency(1234.567, "EUR"), "€1,234.57");
  assert.equal(formatCurrency(1234.5, "INR"), "₹1,234.50");
  assert.match(formatCurrency(1234.5, "XYZ"), /XYZ.*1,234\.50/);
});

test("chat booking and detail price lines extract source amounts for shared display", () => {
  assert.deepEqual(parseCurrencyPriceLine("Price per traveller: EUR 65.61"), {
    label: "Price per traveller: ", amount: 65.61, currency: "EUR",
  });
  assert.deepEqual(parseCurrencyPriceLine("Total for 5 travellers: 328.05 EUR"), {
    label: "Total for 5 travellers: ", amount: 328.05, currency: "EUR",
  });
  assert.equal(parseCurrencyPriceLine("Destination: Paris"), null);
});
