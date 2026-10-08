import { useEffect, useState } from "react";

const rateCache = new Map();
const pendingRates = new Map();

function getInrRate(currency) {
  if (rateCache.has(currency)) {
    return Promise.resolve(rateCache.get(currency));
  }
  if (pendingRates.has(currency)) {
    return pendingRates.get(currency);
  }

  const request = fetch(
    `https://api.frankfurter.dev/v2/rate/${encodeURIComponent(currency)}/INR`
  )
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Exchange-rate service returned ${response.status}`);
      }
      const data = await response.json();
      if (!Number.isFinite(data.rate) || data.rate <= 0) {
        throw new Error("Exchange-rate service returned an invalid rate");
      }
      const result = { rate: data.rate, date: data.date };
      rateCache.set(currency, result);
      return result;
    })
    .finally(() => pendingRates.delete(currency));

  pendingRates.set(currency, request);
  return request;
}

function formatCurrency(value, currency) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export default function InrPrice({
  amount,
  currency = "INR",
  className = "",
}) {
  const sourceCurrency = String(currency || "INR").toUpperCase();
  const [rateState, setRateState] = useState(() => ({
    currency: sourceCurrency,
    quote: sourceCurrency === "INR" ? { rate: 1, date: null } : null,
    unavailable: false,
  }));
  const numericAmount = Number(amount);

  const quote = sourceCurrency === "INR"
    ? { rate: 1, date: null }
    : rateState.currency === sourceCurrency
      ? rateState.quote
      : null;
  const rateUnavailable = (
    sourceCurrency !== "INR"
    && rateState.currency === sourceCurrency
    && rateState.unavailable
  );

  useEffect(() => {
    let active = true;

    if (sourceCurrency === "INR") {
      return () => {
        active = false;
      };
    }

    getInrRate(sourceCurrency)
      .then((result) => {
        if (active) {
          setRateState({
            currency: sourceCurrency,
            quote: result,
            unavailable: false,
          });
        }
      })
      .catch(() => {
        if (active) {
          setRateState({
            currency: sourceCurrency,
            quote: null,
            unavailable: true,
          });
        }
      });

    return () => {
      active = false;
    };
  }, [sourceCurrency]);

  if (amount === null || amount === undefined || !Number.isFinite(numericAmount)) {
    return <span className={className}>—</span>;
  }

  const convertedAmount = quote
    ? formatCurrency(numericAmount * quote.rate, "INR")
    : rateUnavailable
      ? formatCurrency(numericAmount, sourceCurrency)
      : "Converting to INR…";

  return (
    <span className={className}>
      <span>{convertedAmount}</span>
      {sourceCurrency !== "INR" && (
        <span className="mt-1 block text-xs font-normal text-slate-500">
          {quote
            ? `Approx. ${formatCurrency(numericAmount, sourceCurrency)} · reference rate${quote.date ? ` dated ${quote.date}` : ""}`
            : rateUnavailable
              ? "INR conversion unavailable; showing provider currency"
              : "Using the latest available reference rate"}
        </span>
      )}
    </span>
  );
}
