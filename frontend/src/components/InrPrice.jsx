import { useEffect, useState } from "react";
import { getInrRate, getInrPriceDisplay } from "../utils/currency.js";

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

  const display = getInrPriceDisplay(
    amount,
    sourceCurrency,
    quote,
    rateUnavailable,
  );

  return (
    <span className={className}>
      <span>{display.primary}</span>
      {display.secondary && (
        <span className="mt-1 block text-xs font-normal text-slate-500">
          {display.secondary}
        </span>
      )}
    </span>
  );
}
