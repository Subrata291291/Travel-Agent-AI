const rateCache = new Map();
const pendingRates = new Map();

export function getInrRate(currency) {
  const sourceCurrency = String(currency || "").toUpperCase();
  if (rateCache.has(sourceCurrency)) {
    return Promise.resolve(rateCache.get(sourceCurrency));
  }
  if (pendingRates.has(sourceCurrency)) {
    return pendingRates.get(sourceCurrency);
  }

  const request = fetch(
    `https://api.frankfurter.dev/v2/rate/${encodeURIComponent(sourceCurrency)}/INR`
  )
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Exchange-rate service returned ${response.status}`);
      }
      const data = await response.json();
      if (!Number.isFinite(data.rate) || data.rate <= 0 || !data.date) {
        throw new Error("Exchange-rate service returned an invalid quote");
      }
      const result = { rate: data.rate, date: data.date };
      rateCache.set(sourceCurrency, result);
      return result;
    })
    .finally(() => pendingRates.delete(sourceCurrency));

  pendingRates.set(sourceCurrency, request);
  return request;
}

export function formatCurrency(value, currency) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return "—";
  const currencyCode = String(currency || "INR").toUpperCase();
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericValue);
  } catch {
    return `${new Intl.NumberFormat("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericValue)} ${currencyCode}`;
  }
}

export function parseCurrencyPriceLine(line) {
  const match = String(line || "").match(
    /^(\s*(?:Price per traveller|Price per night|Total(?: price)?|Total for \d+ travellers)\s*:\s*)(?:([A-Z]{3})\s*)?([\d,]+(?:\.\d+)?)\s*([A-Z]{3})?\s*$/i,
  );
  const currency = match?.[2] || match?.[4];
  if (!match || !currency) return null;
  const amount = Number(match[3].replaceAll(",", ""));
  return Number.isFinite(amount)
    ? { label: match[1], amount, currency: currency.toUpperCase() }
    : null;
}

// Amounts passed here are always in supplier/source currency. Conversion only
// happens in this display model; the source amount remains untouched.
export function getInrPriceDisplay(amount, currency = "INR", quote = null, unavailable = false) {
  const sourceCurrency = String(currency || "INR").toUpperCase();
  const numericAmount = Number(amount);
  if (amount === null || amount === undefined || !Number.isFinite(numericAmount)) {
    return { primary: "—", secondary: null, converted: false };
  }

  if (sourceCurrency === "INR") {
    return {
      primary: formatCurrency(numericAmount, "INR"),
      secondary: null,
      converted: false,
    };
  }

  if (quote && Number.isFinite(quote.rate) && quote.rate > 0) {
    return {
      primary: formatCurrency(numericAmount * quote.rate, "INR"),
      secondary: `Approx. ${formatCurrency(numericAmount, sourceCurrency)} · reference rate${quote.date ? ` dated ${quote.date}` : ""}`,
      converted: true,
    };
  }

  if (!unavailable) {
    return {
      primary: "Loading INR conversion…",
      secondary: `Supplier price: ${formatCurrency(numericAmount, sourceCurrency)}`,
      converted: false,
    };
  }

  return {
    primary: formatCurrency(numericAmount, sourceCurrency),
    secondary: "INR conversion unavailable; showing provider currency",
    converted: false,
  };
}
