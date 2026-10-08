import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  getBookingDetails,
  cancelBooking,
} from "../services/bookingService";
import InrPrice from "../components/InrPrice";


function BookingDetails() {
  const { bookingId } = useParams();
  const navigate = useNavigate();

  const [booking, setBooking] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  const [showCancelModal, setShowCancelModal] = useState(false);


  // =========================================================
  // LOAD BOOKING
  // =========================================================

  useEffect(() => {
    let mounted = true;

    async function loadBooking() {
      try {
        setLoading(true);
        setError("");

        const data = await getBookingDetails(
          bookingId
        );

        if (mounted) {
          setBooking(data);
        }
      } catch (error) {
        console.error(
          "Failed to load booking:",
          error
        );

        if (mounted) {
          setError(
            error.response?.data?.detail ||
              "Unable to load this booking."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadBooking();

    return () => {
      mounted = false;
    };
  }, [bookingId]);


  // =========================================================
  // CANCEL BOOKING
  // =========================================================

  async function handleCancel() {
    try {
      setCancelling(true);
      setCancelError("");

      const updatedBooking =
        await cancelBooking(bookingId);

      setBooking(updatedBooking);

      setShowCancelModal(false);

    } catch (error) {
      console.error(
        "Failed to cancel booking:",
        error
      );

      setCancelError(
        error.response?.data?.detail ||
          "Unable to cancel this booking."
      );
    } finally {
      setCancelling(false);
    }
  }


  // =========================================================
  // LOADING
  // =========================================================

  if (loading) {
    return <BookingDetailsSkeleton />;
  }


  // =========================================================
  // ERROR
  // =========================================================

  if (error || !booking) {
    return (
      <div className="space-y-6">

        <Link
          to="/my-trips"
          className="inline-flex items-center text-sm font-semibold text-slate-600 hover:text-slate-900"
        >
          ← Back to My Trips
        </Link>

        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center">

          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600">
            !
          </div>

          <h2 className="mt-4 text-lg font-bold text-slate-900">
            Booking not found
          </h2>

          <p className="mt-2 text-sm text-red-700">
            {error || "This booking could not be found."}
          </p>

          <Link
            to="/my-trips"
            className="mt-6 inline-flex rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Back to My Trips
          </Link>

        </div>

      </div>
    );
  }


  // =========================================================
  // BOOKING TYPE
  // =========================================================

  const isHotel =
    Boolean(
      booking.hotel_id ||
      booking.hotel_name ||
      booking.check_in_date
    );

  const status =
    booking.status?.toLowerCase() || "unknown";

  const isCancelled =
    status === "cancelled";

  const isConfirmed =
    status === "confirmed";


  return (
    <div className="mx-auto max-w-6xl space-y-6">


      {/* =====================================================
          BACK
      ====================================================== */}

      <Link
        to="/my-trips"
        className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 transition hover:text-slate-900"
      >
        ← Back to My Trips
      </Link>


      {/* =====================================================
          HEADER
      ====================================================== */}

      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">

        <div>

          <p className="text-sm font-medium text-slate-400">
            Booking details
          </p>

          <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900">
            {isHotel
              ? "Hotel Booking"
              : "Transport Booking"}
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Booking ID:{" "}
            <span className="font-semibold text-slate-700">
              {booking.booking_id}
            </span>
          </p>

        </div>

        <StatusBadge status={status} />

      </div>


      {/* =====================================================
          MAIN BOOKING CARD
      ====================================================== */}

      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">


        {/* ===================================================
            HERO
        ==================================================== */}

        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-8 text-white md:px-8">

          {isHotel ? (
            <HotelHero booking={booking} />
          ) : (
            <TransportHero booking={booking} />
          )}

        </div>


        {/* ===================================================
            DETAILS
        ==================================================== */}

        <div className="p-6 md:p-8">

          {isHotel ? (
            <HotelDetails booking={booking} />
          ) : (
            <TransportDetails booking={booking} />
          )}

        </div>

      </div>


      {/* =====================================================
          PRICE SUMMARY
      ====================================================== */}

      <PriceSummary booking={booking} />


      {/* =====================================================
          BOOKING ACTIONS
      ====================================================== */}

      {isConfirmed && (

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">

            <div>

              <h2 className="font-semibold text-slate-900">
                Manage your booking
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                You can cancel this booking if your plans have changed.
              </p>

            </div>

            <button
              type="button"
              onClick={() => {
                setCancelError("");
                setShowCancelModal(true);
              }}
              className="rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm font-semibold text-red-600 transition hover:bg-red-100"
            >
              Cancel Booking
            </button>

          </div>

        </div>

      )}


      {/* =====================================================
          CANCELLED MESSAGE
      ====================================================== */}

      {isCancelled && (

        <div className="rounded-2xl border border-red-200 bg-red-50 p-6">

          <div className="flex gap-4">

            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
              ×
            </div>

            <div>

              <h2 className="font-semibold text-red-900">
                This booking has been cancelled
              </h2>

              <p className="mt-1 text-sm leading-6 text-red-700">
                This booking is no longer active.
              </p>

            </div>

          </div>

        </div>

      )}


      {/* =====================================================
          CANCEL MODAL
      ====================================================== */}

      {showCancelModal && (

        <CancelModal
          booking={booking}
          cancelling={cancelling}
          error={cancelError}
          onCancel={() =>
            setShowCancelModal(false)
          }
          onConfirm={handleCancel}
        />

      )}

    </div>
  );
}


/* ============================================================
   TRANSPORT HERO
============================================================ */

function TransportHero({
  booking,
}) {
  return (
    <div>

      <div className="flex items-center gap-3">

        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-xl">
          ✈
        </div>

        <div>

          <p className="text-sm text-slate-300">
            {capitalize(
              booking.mode || "Transport"
            )}
          </p>

          <p className="font-semibold">
            {booking.provider || "Travel Provider"}
          </p>

        </div>

      </div>


      <div className="mt-8 grid grid-cols-[1fr_auto_1fr] items-center gap-5">

        <div>

          <p className="text-xs uppercase tracking-wider text-slate-400">
            From
          </p>

          <p className="mt-2 text-2xl font-bold">
            {booking.origin || "—"}
          </p>

          <p className="mt-1 text-sm text-slate-400">
            {formatDateTime(
              booking.departure_time
            )}
          </p>

        </div>


        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
          →
        </div>


        <div className="text-right">

          <p className="text-xs uppercase tracking-wider text-slate-400">
            To
          </p>

          <p className="mt-2 text-2xl font-bold">
            {booking.destination || "—"}
          </p>

          <p className="mt-1 text-sm text-slate-400">
            {formatDateTime(
              booking.arrival_time
            )}
          </p>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   HOTEL HERO
============================================================ */

function HotelHero({
  booking,
}) {
  return (
    <div>

      <div className="flex items-center gap-3">

        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-xl">
          ⌂
        </div>

        <div>

          <p className="text-sm text-slate-300">
            Hotel
          </p>

          <p className="font-semibold">
            {booking.provider || "Hotel Provider"}
          </p>

        </div>

      </div>


      <div className="mt-8">

        <p className="text-3xl font-bold">
          {booking.hotel_name || "Hotel"}
        </p>

        <p className="mt-2 text-slate-300">
          {booking.destination || "—"}
        </p>

      </div>


      <div className="mt-7 grid grid-cols-2 gap-6">

        <div>

          <p className="text-xs uppercase tracking-wider text-slate-400">
            Check-in
          </p>

          <p className="mt-2 font-semibold">
            {formatDate(
              booking.check_in_date
            )}
          </p>

        </div>

        <div>

          <p className="text-xs uppercase tracking-wider text-slate-400">
            Check-out
          </p>

          <p className="mt-2 font-semibold">
            {formatDate(
              booking.check_out_date
            )}
          </p>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   TRANSPORT DETAILS
============================================================ */

function TransportDetails({
  booking,
}) {
  return (
    <div>

      <SectionTitle>
        Journey information
      </SectionTitle>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">

        <InfoItem
          label="Option"
          value={booking.option_id}
        />

        <InfoItem
          label="Mode"
          value={capitalize(booking.mode)}
        />

        <InfoItem
          label="Travellers"
          value={booking.travellers}
        />

        <InfoItem
          label="Duration"
          value={formatDuration(
            booking.duration_minutes
          )}
        />

      </div>


      <div className="my-8 border-t border-slate-100" />


      <SectionTitle>
        Travel times
      </SectionTitle>

      <div className="grid gap-6 sm:grid-cols-2">

        <InfoItem
          label="Departure"
          value={formatDateTime(
            booking.departure_time
          )}
        />

        <InfoItem
          label="Arrival"
          value={formatDateTime(
            booking.arrival_time
          )}
        />

      </div>


      <div className="my-8 border-t border-slate-100" />


      <SectionTitle>
        Provider
      </SectionTitle>

      <InfoItem
        label="Provider"
        value={booking.provider}
      />

    </div>
  );
}


/* ============================================================
   HOTEL DETAILS
============================================================ */

function HotelDetails({
  booking,
}) {
  return (
    <div>

      <SectionTitle>
        Stay information
      </SectionTitle>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">

        <InfoItem
          label="Hotel"
          value={booking.hotel_name}
        />

        <InfoItem
          label="Destination"
          value={booking.destination}
        />

        <InfoItem
          label="Travellers"
          value={booking.travellers}
        />

        <InfoItem
          label="Nights"
          value={booking.nights}
        />

      </div>


      <div className="my-8 border-t border-slate-100" />


      <SectionTitle>
        Stay dates
      </SectionTitle>

      <div className="grid gap-6 sm:grid-cols-2">

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


      <div className="my-8 border-t border-slate-100" />


      <SectionTitle>
        Provider
      </SectionTitle>

      <InfoItem
        label="Provider"
        value={booking.provider}
      />

    </div>
  );
}


/* ============================================================
   PRICE SUMMARY
============================================================ */

function PriceSummary({
  booking,
}) {
  const isHotel =
    Boolean(
      booking.hotel_id ||
      booking.hotel_name
    );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

      <h2 className="font-semibold text-slate-900">
        Price summary
      </h2>

      <div className="mt-5 space-y-4">

        {isHotel ? (
          <>

            <PriceRow
              label="Price per night"
              value={(
                <InrPrice
                  amount={booking.price_per_night}
                  currency={booking.currency}
                />
              )}
            />

            <PriceRow
              label="Nights"
              value={booking.nights}
            />

          </>
        ) : (
          <PriceRow
            label="Price per traveller"
            value={(
              <InrPrice
                amount={booking.price}
                currency={booking.currency}
              />
            )}
          />
        )}

        <div className="border-t border-slate-100 pt-4">

          <div className="flex items-center justify-between">

            <span className="font-semibold text-slate-900">
              Total
            </span>

            <span className="text-2xl font-bold text-slate-900">
              <InrPrice
                amount={booking.total_price}
                currency={booking.currency}
                className="text-right"
              />
            </span>

          </div>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   PRICE ROW
============================================================ */

function PriceRow({
  label,
  value,
}) {
  return (
    <div className="flex items-center justify-between text-sm">

      <span className="text-slate-500">
        {label}
      </span>

      <span className="font-medium text-slate-700">
        {value}
      </span>

    </div>
  );
}


/* ============================================================
   INFO ITEM
============================================================ */

function InfoItem({
  label,
  value,
}) {
  return (
    <div>

      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
        {label}
      </p>

      <p className="mt-2 text-sm font-semibold text-slate-800">
        {value ?? "—"}
      </p>

    </div>
  );
}


/* ============================================================
   SECTION TITLE
============================================================ */

function SectionTitle({
  children,
}) {
  return (
    <h2 className="mb-5 text-base font-semibold text-slate-900">
      {children}
    </h2>
  );
}


/* ============================================================
   STATUS BADGE
============================================================ */

function StatusBadge({
  status,
}) {
  const styles = {
    confirmed:
      "border-emerald-200 bg-emerald-50 text-emerald-700",

    cancelled:
      "border-red-200 bg-red-50 text-red-700",

    pending:
      "border-amber-200 bg-amber-50 text-amber-700",

    unknown:
      "border-slate-200 bg-slate-50 text-slate-600",
  };

  return (
    <span
      className={[
        "inline-flex rounded-full border px-4 py-2 text-xs font-semibold capitalize",
        styles[status] || styles.unknown,
      ].join(" ")}
    >
      {status}
    </span>
  );
}


/* ============================================================
   CANCEL MODAL
============================================================ */

function CancelModal({
  booking,
  cancelling,
  error,
  onCancel,
  onConfirm,
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-5 backdrop-blur-sm">

      <div className="w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl">

        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-xl text-red-600">
          !
        </div>

        <h2 className="mt-5 text-xl font-bold text-slate-900">
          Cancel this booking?
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          You're about to cancel booking{" "}
          <span className="font-semibold text-slate-700">
            {booking.booking_id}
          </span>
          .
        </p>

        <p className="mt-3 text-sm leading-6 text-slate-500">
          This action will change the booking status to
          cancelled.
        </p>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-7 flex gap-3">

          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            Keep booking
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={cancelling}
            className="flex-1 rounded-xl bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {cancelling
              ? "Cancelling..."
              : "Yes, cancel"}
          </button>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   LOADING SKELETON
============================================================ */

function BookingDetailsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">

      <div className="h-5 w-32 rounded bg-slate-200" />

      <div className="h-10 w-72 rounded bg-slate-200" />

      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white">

        <div className="h-72 bg-slate-200" />

        <div className="space-y-5 p-8">

          <div className="h-5 w-48 rounded bg-slate-200" />

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">

            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-16 rounded-xl bg-slate-100"
              />
            ))}

          </div>

        </div>

      </div>

    </div>
  );
}


/* ============================================================
   HELPERS
============================================================ */

function capitalize(value) {
  if (!value) {
    return "—";
  }

  return String(value)
    .charAt(0)
    .toUpperCase() +
    String(value).slice(1);
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


function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


function formatDuration(minutes) {
  if (
    minutes === null ||
    minutes === undefined
  ) {
    return "—";
  }

  const totalMinutes = Number(minutes);

  if (Number.isNaN(totalMinutes)) {
    return String(minutes);
  }

  const hours = Math.floor(
    totalMinutes / 60
  );

  const remainingMinutes =
    totalMinutes % 60;

  if (hours === 0) {
    return `${remainingMinutes} min`;
  }

  if (remainingMinutes === 0) {
    return `${hours} hr`;
  }

  return `${hours} hr ${remainingMinutes} min`;
}


export default BookingDetails;
