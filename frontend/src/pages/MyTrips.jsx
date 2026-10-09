import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getBookings } from "../services/bookingService";
import InrPrice from "../components/InrPrice";

function MyTrips() {
  const [bookings, setBookings] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filter, setFilter] = useState("all");

  // ========================================================
  // LOAD BOOKINGS
  // ========================================================

  useEffect(() => {
    let mounted = true;

    async function loadBookings() {
      try {
        setLoading(true);
        setError("");

        const data = await getBookings();

        const bookingList = Array.isArray(data)
          ? data
          : data?.bookings || [];

        if (mounted) {
          setBookings(bookingList);
        }
      } catch (error) {
        console.error(
          "Failed to load bookings:",
          error
        );

        if (mounted) {
          setError(
            error.response?.data?.detail ||
              "Unable to load your bookings."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadBookings();

    return () => {
      mounted = false;
    };
  }, []);

  // ========================================================
  // FILTER BOOKINGS
  // ========================================================

  const filteredBookings = useMemo(() => {
    if (filter === "all") {
      return bookings;
    }

    return bookings.filter(
      (booking) =>
        booking.status?.toLowerCase() === filter
    );
  }, [bookings, filter]);

  // ========================================================
  // COUNTS
  // ========================================================

  const counts = useMemo(() => {
    return {
      all: bookings.length,

      confirmed: bookings.filter(
        (booking) =>
          booking.status?.toLowerCase() === "confirmed"
      ).length,

      cancelled: bookings.filter(
        (booking) =>
          booking.status?.toLowerCase() === "cancelled"
      ).length,
    };
  }, [bookings]);

  // ========================================================
  // LOADING
  // ========================================================

  if (loading) {
    return (
      <div className="space-y-6">

        <PageHeader />

        <div className="grid gap-5 lg:grid-cols-2">

          {[1, 2, 3, 4].map((item) => (
            <BookingSkeleton key={item} />
          ))}

        </div>

      </div>
    );
  }

  // ========================================================
  // PAGE
  // ========================================================

  return (
    <div className="space-y-7">

      {/* ====================================================
          HEADER
      ===================================================== */}

      <PageHeader />

      {/* ====================================================
          SUMMARY
      ===================================================== */}

      <div className="grid gap-4 sm:grid-cols-3">

        <SummaryCard
          label="All bookings"
          value={counts.all}
        />

        <SummaryCard
          label="Confirmed"
          value={counts.confirmed}
        />

        <SummaryCard
          label="Cancelled"
          value={counts.cancelled}
        />

      </div>

      {/* ====================================================
          ERROR
      ===================================================== */}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ====================================================
          FILTER
      ===================================================== */}

      <div className="flex flex-wrap items-center gap-2">

        <FilterButton
          active={filter === "all"}
          onClick={() => setFilter("all")}
        >
          All
        </FilterButton>

        <FilterButton
          active={filter === "confirmed"}
          onClick={() => setFilter("confirmed")}
        >
          Confirmed
        </FilterButton>

        <FilterButton
          active={filter === "cancelled"}
          onClick={() => setFilter("cancelled")}
        >
          Cancelled
        </FilterButton>

      </div>

      {/* ====================================================
          EMPTY STATE
      ===================================================== */}

      {!filteredBookings.length && !error && (
        <EmptyState />
      )}

      {/* ====================================================
          BOOKINGS
      ===================================================== */}

      {filteredBookings.length > 0 && (
        <div className="grid gap-5 xl:grid-cols-2">

          {filteredBookings.map((booking) => (
            <BookingCard
              key={booking.booking_id}
              booking={booking}
            />
          ))}

        </div>
      )}

    </div>
  );
}


/* ==========================================================
   PAGE HEADER
========================================================== */

function PageHeader() {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">

      <div>
        <p className="text-sm font-medium text-slate-400">
          Travel management
        </p>

        <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
          My Trips
        </h1>

        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
          View and manage all your transport and hotel
          bookings from one place.
        </p>
      </div>

      <Link
        to="/chat"
        className="inline-flex w-fit items-center rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
      >
        + Plan a new trip
      </Link>

    </div>
  );
}


/* ==========================================================
   SUMMARY CARD
========================================================== */

function SummaryCard({
  label,
  value,
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

      <p className="text-sm font-medium text-slate-500">
        {label}
      </p>

      <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
        {value}
      </p>

    </div>
  );
}


/* ==========================================================
   FILTER BUTTON
========================================================== */

function FilterButton({
  active,
  onClick,
  children,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-xl px-4 py-2 text-sm font-medium transition",
        active
          ? "bg-slate-900 text-white shadow-sm"
          : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50",
      ].join(" ")}
    >
      {children}
    </button>
  );
}


/* ==========================================================
   BOOKING CARD
========================================================== */

function BookingCard({
  booking,
}) {
  const isHotel =
    Boolean(
      booking.hotel_id ||
      booking.hotel_name ||
      booking.check_in_date
    );

  const status =
    booking.status?.toLowerCase() || "unknown";
  const isTrain =
    booking.mode?.toLowerCase() === "train";

  return (
    <Link
      to={`/my-trips/${booking.booking_id}`}
      className="
        group
        block
        overflow-hidden
        rounded-2xl
        border
        border-slate-200
        bg-white
        shadow-sm
        transition-all
        duration-200
        hover:-translate-y-1
        hover:border-slate-300
        hover:shadow-lg
      "
    >

      {/* Top */}
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">

        <div className="flex items-center gap-3">

          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-lg">
            {isHotel ? "⌂" : isTrain ? (
              <svg
                aria-label="Train"
                role="img"
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="5" y="3" width="14" height="15" rx="3" />
                <path d="M8 7h3v4H8zM13 7h3v4h-3zM8 15h8M8 21l2-3m6 3-2-3M5 13h14" />
                <circle cx="8" cy="15" r=".5" fill="currentColor" />
                <circle cx="16" cy="15" r=".5" fill="currentColor" />
              </svg>
            ) : "✈"}
          </div>

          <div>
            <p className="text-sm font-semibold capitalize text-slate-900">
              {isHotel
                ? "Hotel Booking"
                : `${booking.mode || "Transport"} Booking`}
            </p>

            <p className="mt-0.5 text-xs text-slate-400">
              {booking.booking_id}
            </p>
          </div>

        </div>

        <StatusBadge status={status} />

      </div>

      {/* Content */}
      <div className="p-5">

        {isHotel ? (
          <HotelBookingContent
            booking={booking}
          />
        ) : (
          <TransportBookingContent
            booking={booking}
          />
        )}

      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">

        <div>
          <p className="text-xs text-slate-400">
            Total
          </p>

          <InrPrice
            amount={booking.total_price}
            currency={booking.currency}
            className="mt-1 block text-lg font-bold text-slate-900"
          />
        </div>

        <span className="text-sm font-semibold text-slate-700 transition-transform group-hover:translate-x-1">
          View details →
        </span>

      </div>

    </Link>
  );
}


/* ==========================================================
   TRANSPORT CONTENT
========================================================== */

function TransportBookingContent({
  booking,
}) {
  return (
    <div className="space-y-5">

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">

        <div>
          <p className="text-xs text-slate-400">
            From
          </p>

          <p className="mt-1 font-semibold text-slate-900">
            {booking.origin || "—"}
          </p>
        </div>

        <div className="text-slate-300">
          →
        </div>

        <div className="text-right">
          <p className="text-xs text-slate-400">
            To
          </p>

          <p className="mt-1 font-semibold text-slate-900">
            {booking.destination || "—"}
          </p>
        </div>

      </div>

      <div className="grid grid-cols-2 gap-4">

        <InfoItem
          label="Departure"
          value={formatDate(
            booking.departure_time
          )}
        />

        <InfoItem
          label="Travellers"
          value={
            booking.travellers
              ? `${booking.travellers}`
              : "—"
          }
        />

      </div>

    </div>
  );
}


/* ==========================================================
   HOTEL CONTENT
========================================================== */

function HotelBookingContent({
  booking,
}) {
  return (
    <div className="space-y-5">

      <div>

        <p className="text-xs text-slate-400">
          Hotel
        </p>

        <p className="mt-1 text-lg font-semibold text-slate-900">
          {booking.hotel_name || "Hotel"}
        </p>

        <p className="mt-1 text-sm text-slate-500">
          {booking.destination || "—"}
        </p>

      </div>

      <div className="grid grid-cols-2 gap-4">

        <InfoItem
          label="Check-in"
          value={formatDate(
            booking.check_in_date
          )}
        />

        <InfoItem
          label="Check-out"
          value={formatDate(
            booking.check_out_date
          )}
        />

      </div>

    </div>
  );
}


/* ==========================================================
   INFO ITEM
========================================================== */

function InfoItem({
  label,
  value,
}) {
  return (
    <div>
      <p className="text-xs text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-sm font-medium text-slate-700">
        {value}
      </p>
    </div>
  );
}


/* ==========================================================
   STATUS
========================================================== */

function StatusBadge({
  status,
}) {
  const styles = {
    confirmed:
      "bg-emerald-50 text-emerald-700 border-emerald-200",

    cancelled:
      "bg-red-50 text-red-700 border-red-200",

    pending:
      "bg-amber-50 text-amber-700 border-amber-200",

    unknown:
      "bg-slate-50 text-slate-600 border-slate-200",
  };

  return (
    <span
      className={[
        "rounded-full border px-3 py-1 text-xs font-semibold capitalize",
        styles[status] || styles.unknown,
      ].join(" ")}
    >
      {status}
    </span>
  );
}


/* ==========================================================
   EMPTY STATE
========================================================== */

function EmptyState() {
  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">

      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-xl">
        ✈
      </div>

      <h2 className="mt-5 text-lg font-bold text-slate-900">
        No trips found
      </h2>

      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
        You don't have any bookings in this category yet.
        Start planning your next journey with the AI travel
        assistant.
      </p>

      <Link
        to="/chat"
        className="mt-6 inline-flex rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        Plan a trip
      </Link>

    </div>
  );
}


/* ==========================================================
   LOADING SKELETON
========================================================== */

function BookingSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

      <div className="animate-pulse p-5">

        <div className="flex items-center gap-3">

          <div className="h-11 w-11 rounded-xl bg-slate-200" />

          <div className="space-y-2">
            <div className="h-4 w-32 rounded bg-slate-200" />
            <div className="h-3 w-24 rounded bg-slate-100" />
          </div>

        </div>

        <div className="mt-7 grid grid-cols-2 gap-5">

          <div className="space-y-2">
            <div className="h-3 w-16 rounded bg-slate-100" />
            <div className="h-4 w-28 rounded bg-slate-200" />
          </div>

          <div className="space-y-2">
            <div className="h-3 w-16 rounded bg-slate-100" />
            <div className="h-4 w-28 rounded bg-slate-200" />
          </div>

        </div>

      </div>

    </div>
  );
}


/* ==========================================================
   HELPERS
========================================================== */

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}


export default MyTrips;
