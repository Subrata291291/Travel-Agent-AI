import {
  useEffect,
  useRef,
  useState,
} from "react";

import { sendChatMessage } from "../services/chatService";
import InrPrice from "../components/InrPrice";


function Chat() {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your AI travel assistant. Tell me where you'd like to go, when you're travelling, and what you need help with.",
    },
  ]);

  const [input, setInput] = useState("");

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const messagesEndRef = useRef(null);

  const textareaRef = useRef(null);


  // =========================================================
  // SESSION ID
  // =========================================================

  const [sessionId] = useState(() => {
    const existing =
      sessionStorage.getItem(
        "travel_agent_session_id"
      );

    if (existing) {
      return existing;
    }

    const newSession =
      `web-${crypto.randomUUID()}`;

    sessionStorage.setItem(
      "travel_agent_session_id",
      newSession
    );

    return newSession;
  });


  // =========================================================
  // AUTO SCROLL
  // =========================================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);


  // =========================================================
  // SEND MESSAGE
  // =========================================================

  async function handleSend(messageOverride = input) {
    // React passes a MouseEvent to onClick handlers. Only use the override
    // when it is a message string (option-card quick replies); otherwise send
    // the text currently in the composer.
    const message = (
      typeof messageOverride === "string"
        ? messageOverride
        : input
    ).trim();

    if (!message || loading) {
      return;
    }

    setError("");

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setInput("");

    try {
      setLoading(true);

      const result =
        await sendChatMessage({
          message,
          sessionId,
        });

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          result.answer ||
          "I couldn't generate a response.",
        data: result,
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);

    } catch (err) {
      console.error(
        "Chat request failed:",
        err
      );

      const message =
        err.response?.data?.detail ||
        "Something went wrong while contacting the travel assistant.";

      setError(message);

    } finally {
      setLoading(false);

      setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    }
  }


  // =========================================================
  // ENTER KEY
  // =========================================================

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      handleSend();
    }
  }


  // =========================================================
  // SUGGESTED PROMPT
  // =========================================================

  function handleSuggestion(text) {
    setInput(text);

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 0);
  }


  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-[600px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">

      {/* ====================================================
          HEADER
      ===================================================== */}

      <ChatHeader
        sessionId={sessionId}
      />


      {/* ====================================================
          MESSAGES
      ===================================================== */}

      <div className="flex-1 overflow-y-auto bg-slate-50/70 px-4 py-6 sm:px-6">

        <div className="mx-auto max-w-4xl space-y-6">

          {messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              onSelect={handleSend}
            />
          ))}


          {loading && (
            <TypingIndicator />
          )}


          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}


          <div ref={messagesEndRef} />

        </div>

      </div>


      {/* ====================================================
          SUGGESTIONS
      ===================================================== */}

      {messages.length <= 1 &&
        !loading && (
          <div className="border-t border-slate-100 bg-white px-4 py-4 sm:px-6">

            <div className="mx-auto max-w-4xl">

              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Try asking
              </p>

              <div className="flex flex-wrap gap-2">

                <Suggestion
                  onClick={() =>
                    handleSuggestion(
                      "I want to plan a trip to Goa"
                    )
                  }
                >
                  Plan a trip to Goa
                </Suggestion>

                <Suggestion
                  onClick={() =>
                    handleSuggestion(
                      "Find transport from Kolkata to Goa"
                    )
                  }
                >
                  Find transport
                </Suggestion>

                <Suggestion
                  onClick={() =>
                    handleSuggestion(
                      "Find hotels in Goa"
                    )
                  }
                >
                  Find a hotel
                </Suggestion>

                <Suggestion
                  onClick={() =>
                    handleSuggestion(
                      "Show my bookings"
                    )
                  }
                >
                  Show my bookings
                </Suggestion>

              </div>

            </div>

          </div>
        )}


      {/* ====================================================
          INPUT
      ===================================================== */}

      <div className="border-t border-slate-200 bg-white px-4 py-4 sm:px-6">

        <div className="mx-auto max-w-4xl">

          <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-2 shadow-sm transition focus-within:border-slate-400 focus-within:bg-white focus-within:shadow-md">

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              disabled={loading}
              rows={1}
              placeholder="Ask me about your next trip..."
              className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
            />

            <button
              type="button"
              onClick={handleSend}
              disabled={
                !input.trim() ||
                loading
              }
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
              aria-label="Send message"
            >
              ↑
            </button>

          </div>

          <p className="mt-2 text-center text-xs text-slate-400">
            Press Enter to send · Shift + Enter for a new line
          </p>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   CHAT HEADER
============================================================ */

function ChatHeader({
  sessionId,
}) {
  return (
    <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-6">

      <div className="flex items-center gap-3">

        <div className="relative">

          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-lg text-white">
            ✦
          </div>

          <span className="absolute -bottom-1 -right-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-emerald-500" />

        </div>

        <div>

          <h1 className="font-semibold text-slate-900">
            AI Travel Agent
          </h1>

          <p className="text-xs text-emerald-600">
            Online · Ready to help
          </p>

        </div>

      </div>


      <div className="hidden text-right sm:block">

        <p className="text-[10px] uppercase tracking-wider text-slate-400">
          Session
        </p>

        <p className="mt-0.5 max-w-[180px] truncate font-mono text-xs text-slate-500">
          {sessionId}
        </p>

      </div>

    </div>
  );
}


/* ============================================================
   MESSAGE
============================================================ */

function Message({
  message,
  onSelect,
}) {
  const isUser =
    message.role === "user";

  return (
    <div
      className={[
        "flex gap-3",
        isUser
          ? "justify-end"
          : "justify-start",
      ].join(" ")}
    >

      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-sm text-white">
          ✦
        </div>
      )}


      <div
        className={[
          "max-w-[85%] sm:max-w-[75%]",
          isUser
            ? "order-first"
            : "",
        ].join(" ")}
      >

        <div
          className={[
            "rounded-2xl px-4 py-3 text-sm leading-6",
            isUser
              ? "rounded-br-md bg-slate-900 text-white"
              : "rounded-bl-md border border-slate-200 bg-white text-slate-700 shadow-sm",
          ].join(" ")}
        >
          <MessageText
            content={assistantDisplayContent(message)}
            isUser={isUser}
          />
        </div>


        {/* Structured agent results */}

        {!isUser &&
          message.data && (
            <AgentResult
              data={message.data}
              onSelect={onSelect}
            />
          )}

      </div>


      {isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-200 text-sm font-semibold text-slate-700">
          You
        </div>
      )}

    </div>
  );
}


/* ============================================================
   MESSAGE TEXT
============================================================ */

function MessageText({
  content,
  isUser,
}) {
  return (
    <div
      className={
        isUser
          ? "whitespace-pre-wrap"
          : "whitespace-pre-wrap"
      }
    >
      {content}
    </div>
  );
}


/* ============================================================
   AGENT RESULT
============================================================ */

function AgentResult({
  data,
  onSelect,
}) {
  const transportOptions =
    data.transport_options || [];

  const hotelOptions =
    data.hotel_options || [];

  const booking =
    data.booking;

  return (
    <div className="mt-3 space-y-3">

      {/* ==================================================
          TRANSPORT OPTIONS
      =================================================== */}

      {transportOptions.length > 0 && (
        <div>

          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Transport options · not booked
          </p>

          <div className="space-y-2">

            {transportOptions.map(
              (option, index) => (
                <TransportCard
                  key={
                    option.option_id ||
                    index
                  }
                  option={option}
                  onSelect={onSelect}
                />
              )
            )}

          </div>

        </div>
      )}


      {/* ==================================================
          HOTEL OPTIONS
      =================================================== */}

      {hotelOptions.length > 0 && (
        <div>

          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Hotel options · not booked
          </p>

          <div className="space-y-2">

            {hotelOptions.map(
              (option, index) => (
                <HotelCard
                  key={
                    option.hotel_id ||
                    index
                  }
                  option={option}
                  onSelect={onSelect}
                />
              )
            )}

          </div>

        </div>
      )}


      {/* ==================================================
          BOOKING
      =================================================== */}

      {booking && (
        <BookingResult
          booking={booking}
        />
      )}

    </div>
  );
}


/* ============================================================
   TRANSPORT CARD
============================================================ */

function TransportCard({
  option,
  onSelect,
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">

      <div className="flex items-start justify-between gap-4">

        <div>

          <p className="font-semibold capitalize text-slate-900">
            {option.mode ||
              "Transport"}
          </p>

          <p className="mt-1 text-xs text-slate-400">
            {option.provider ||
              "Provider"}
          </p>

        </div>

        <span className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-[10px] font-semibold text-slate-600">
          {option.option_id ||
            "OPTION"}
        </span>

      </div>


      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">

        <div>

          <p className="text-xs text-slate-400">
            From
          </p>

          <p className="mt-1 font-semibold text-slate-800">
            {option.origin ||
              "—"}
          </p>

        </div>

        <span className="text-slate-300">
          →
        </span>

        <div className="text-right">

          <p className="text-xs text-slate-400">
            To
          </p>

          <p className="mt-1 font-semibold text-slate-800">
            {option.destination ||
              "—"}
          </p>

        </div>

      </div>


      <div className="mt-4 flex items-end justify-between border-t border-slate-100 pt-3">

        <div>

          <p className="text-xs text-slate-400">
            Travellers
          </p>

          <p className="mt-1 text-sm font-medium text-slate-700">
            {option.travellers ||
              "—"}
          </p>

        </div>

        <div className="text-right">

          <p className="text-xs text-slate-400">
            {option.total_price != null ? "Total price" : "Price"}
          </p>

          <InrPrice
            amount={option.total_price ?? option.price}
            currency={option.currency}
            className="mt-1 block font-bold text-slate-900"
          />

        </div>

      </div>

      <button
        type="button"
        onClick={() => onSelect?.(`I choose ${option.option_id}`)}
        className="mt-4 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
      >
        Choose this option
      </button>

    </div>
  );
}


/* ============================================================
   HOTEL CARD
============================================================ */

function HotelCard({
  option,
  onSelect,
}) {
  const nights = getNightCount(
    option.check_in_date,
    option.check_out_date
  );
  const total = option.total_price ?? (
    nights > 0 && option.price_per_night != null
      ? nights * Number(option.price_per_night)
      : null
  );
  const isDemo = /mock|demo/i.test(option.provider || "");

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">

      <div className="flex items-start justify-between gap-4">

        <div>

          <p className="font-semibold text-slate-900">
            {option.name || option.hotel_name ||
              "Hotel"}
          </p>

          <p className="mt-1 text-xs text-slate-400">
            {option.destination ||
              "—"}
          </p>

        </div>

        {option.rating && (
          <span className="rounded-lg bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
            ★ {option.rating}
          </span>
        )}

      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        {option.hotel_id && <span>{option.hotel_id}</span>}
        {option.provider && <span>· {option.provider}</span>}
        {isDemo && (
          <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-700">
            Demo data
          </span>
        )}
      </div>


      <div className="mt-4 grid grid-cols-2 gap-4">

        <div>

          <p className="text-xs text-slate-400">
            Check-in
          </p>

          <p className="mt-1 text-sm font-medium text-slate-700">
            {formatDate(
              option.check_in_date
            )}
          </p>

        </div>

        <div>

          <p className="text-xs text-slate-400">
            Check-out
          </p>

          <p className="mt-1 text-sm font-medium text-slate-700">
            {formatDate(
              option.check_out_date
            )}
          </p>

        </div>

      </div>


      <div className="mt-4 flex items-end justify-between border-t border-slate-100 pt-3">

        <div>

          <p className="text-xs text-slate-400">
            Nights
          </p>

          <p className="mt-1 text-sm font-medium text-slate-700">
            {nights > 0 ? nights : "—"}
          </p>

        </div>

        <div className="text-right">

          <p className="text-xs text-slate-400">
            Total
          </p>

          <InrPrice
            amount={total}
            currency={option.currency}
            className="mt-1 block font-bold text-slate-900"
          />

        </div>

      </div>

      <button
        type="button"
        onClick={() => onSelect?.(`I choose ${option.hotel_id}`)}
        className="mt-4 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
      >
        Choose this hotel
      </button>

    </div>
  );
}


/* ============================================================
   BOOKING RESULT
============================================================ */

function BookingResult({
  booking,
}) {
  const isCancelled =
    booking.status?.toLowerCase() ===
    "cancelled";

  return (
    <div
      className={[
        "rounded-xl border p-4",
        isCancelled
          ? "border-red-200 bg-red-50"
          : "border-amber-200 bg-amber-50",
      ].join(" ")}
    >

      <div className="flex items-start gap-3">

        <div
          className={[
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-semibold",
            isCancelled
              ? "bg-red-100 text-red-600"
              : "bg-amber-100 text-amber-700",
          ].join(" ")}
        >
          {isCancelled ? "×" : "i"}
        </div>

        <div className="min-w-0">

          <p className="font-semibold text-slate-900">
            {isCancelled
              ? "Booking cancelled"
              : "Booking record saved"}
          </p>

          <p className="mt-1 font-mono text-xs text-slate-500">
            {booking.booking_id ||
              "Booking ID unavailable"}
          </p>

          {booking.status && (
            <p className="mt-2 text-xs capitalize text-slate-500">
              Status: {booking.status}
            </p>
          )}

          {!isCancelled && (
            <p className="mt-2 max-w-xl text-xs leading-5 text-amber-800">
              This is the app's local record. A supplier reservation and customer payment are not completed by this chat yet.
            </p>
          )}

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   TYPING INDICATOR
============================================================ */

function TypingIndicator() {
  return (
    <div className="flex gap-3">

      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-sm text-white">
        ✦
      </div>

      <div className="rounded-2xl rounded-bl-md border border-slate-200 bg-white px-5 py-4 shadow-sm">

        <div className="flex gap-1.5">

          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />

          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />

          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   SUGGESTION
============================================================ */

function Suggestion({
  children,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-medium text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
    >
      {children}
    </button>
  );
}


/* ============================================================
   HELPERS
============================================================ */

function assistantDisplayContent(message) {
  const data = message.data;
  if (!data) return message.content;

  if (data.booking) {
    if (data.booking.status?.toLowerCase() === "cancelled") {
      return message.content;
    }
    return "I saved the booking record. The card below shows its app status; this chat has not completed a supplier reservation or customer payment.";
  }

  const hotels = data.hotel_options || [];
  const transport = data.transport_options || [];
  if (hotels.length) {
    return `I found ${hotels.length} hotel ${hotels.length === 1 ? "option" : "options"}. Review the dates and total stay price below, then choose one to continue. These are search results, not bookings.`;
  }
  if (transport.length) {
    return `I found ${transport.length} transport ${transport.length === 1 ? "option" : "options"}. Compare the details below and choose one to continue. These are search results, not bookings.`;
  }
  return message.content;
}

function getNightCount(checkIn, checkOut) {
  if (!checkIn || !checkOut) return 0;
  const start = Date.parse(`${checkIn}T00:00:00Z`);
  const end = Date.parse(`${checkOut}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return 0;
  return Math.max(0, Math.round((end - start) / 86_400_000));
}

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }
  );
}


export default Chat;
