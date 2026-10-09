import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { getBookings } from "../services/bookingService";
import { getUserDisplayName } from "../utils/userDisplay";

function Dashboard() {
  const { user } = useAuth();

  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

        /*
         * Unified booking APIs commonly return:
         *
         * {
         *   bookings: [...]
         * }
         *
         * We normalize that here so the rest of
         * the dashboard always works with an array.
         */
        const bookingList = Array.isArray(data)
          ? data
          : data?.bookings || [];

        if (mounted) {
          setBookings(bookingList);
        }
      } catch (err) {
        console.error("Failed to load bookings:", err);

        if (mounted) {
          setError(
            err.response?.data?.detail ||
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
  // CALCULATE DASHBOARD STATISTICS
  // ========================================================

  const stats = useMemo(() => {
    const total = bookings.length;

    const cancelled = bookings.filter(
      (booking) =>
        booking.status?.toLowerCase() === "cancelled"
    ).length;

    const hotels = bookings.filter(
      (booking) =>
        Boolean(
          booking.hotel_id ||
          booking.hotel_name ||
          booking.check_in_date
        )
    ).length;

    const upcoming = bookings.filter((booking) => {
      if (booking.status?.toLowerCase() === "cancelled") {
        return false;
      }

      const date =
        booking.departure_time ||
        booking.check_in_date;

      if (!date) {
        return false;
      }

      return new Date(date) >= new Date();
    }).length;

    return {
      total,
      upcoming,
      hotels,
      cancelled,
    };
  }, [bookings]);

  return (
    <div className="space-y-8">

      {/* =====================================================
          HERO
      ====================================================== */}

      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 p-7 text-white shadow-xl sm:p-9">

        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/5" />

        <div className="absolute -bottom-32 right-20 h-72 w-72 rounded-full bg-blue-500/10" />

        <div className="relative max-w-2xl">

          <p className="mb-3 text-sm font-medium text-slate-400">
            Your personal travel workspace
          </p>

          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Where will your next journey take you?
          </h2>

          <p className="mt-4 max-w-xl text-sm leading-6 text-slate-300 sm:text-base">
            Plan trips, discover transport and hotels,
            make bookings, and manage everything from one
            intelligent travel assistant.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">

            <Link
              to="/chat"
              className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
            >
              Start planning →
            </Link>

            <Link
              to="/my-trips"
              className="rounded-xl border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/15"
            >
              View my trips
            </Link>

          </div>

        </div>
      </section>

      {/* =====================================================
          WELCOME
      ====================================================== */}

      <section>
        <p className="text-sm font-medium text-slate-400">
          Welcome back
        </p>

        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
          {getUserDisplayName(user)} 👋
        </h1>
      </section>

      {/* =====================================================
          ERROR
      ====================================================== */}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* =====================================================
          STATISTICS
      ====================================================== */}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Total Trips"
          value={loading ? "—" : stats.total}
          description="All your bookings"
          icon="▣"
        />

        <StatCard
          label="Upcoming"
          value={loading ? "—" : stats.upcoming}
          description="Future journeys"
          icon="✈"
        />

        <StatCard
          label="Hotels"
          value={loading ? "—" : stats.hotels}
          description="Hotel bookings"
          icon="⌂"
        />

        <StatCard
          label="Cancelled"
          value={loading ? "—" : stats.cancelled}
          description="Cancelled bookings"
          icon="↻"
        />

      </section>

      {/* =====================================================
          QUICK ACTIONS
      ====================================================== */}

      <section>

        <div className="mb-4">
          <h2 className="text-lg font-bold text-slate-900">
            Quick actions
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Get started with your travel assistant
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">

          <ActionCard
            to="/chat"
            icon="✦"
            title="Plan a trip"
            description="Tell the AI where you want to go and let it plan your journey."
          />

          <ActionCard
            to="/my-trips"
            icon="▣"
            title="View my trips"
            description="See your bookings, travel details and current status."
          />

          <ActionCard
            to="/chat"
            icon="?"
            title="Ask the AI"
            description="Find transport, hotels or get help with an existing booking."
          />

        </div>

      </section>

    </div>
  );
}


/* =========================================================
   STAT CARD
========================================================= */

function StatCard({
  label,
  value,
  description,
  icon,
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">

      <div className="flex items-start justify-between">

        <div>
          <p className="text-sm font-medium text-slate-500">
            {label}
          </p>

          <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
            {value}
          </p>
        </div>

        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-lg text-slate-700">
          {icon}
        </div>

      </div>

      <p className="mt-3 text-xs text-slate-400">
        {description}
      </p>

    </div>
  );
}


/* =========================================================
   ACTION CARD
========================================================= */

function ActionCard({
  to,
  icon,
  title,
  description,
}) {
  return (
    <Link
      to={to}
      className="
        group
        block
        cursor-pointer
        rounded-2xl
        border border-slate-200
        bg-white
        p-6
        shadow-sm
        transition-all
        duration-200
        hover:-translate-y-1
        hover:border-slate-300
        hover:shadow-lg
        focus:outline-none
        focus:ring-2
        focus:ring-slate-400
        focus:ring-offset-2
      "
    >
      {/* Icon */}
      <div
        className="
          flex
          h-11
          w-11
          items-center
          justify-center
          rounded-xl
          bg-slate-900
          text-lg
          text-white
          transition-transform
          duration-200
          group-hover:scale-105
        "
      >
        {icon}
      </div>

      {/* Title */}
      <h3 className="mt-5 font-semibold text-slate-900">
        {title}
      </h3>

      {/* Description */}
      <p className="mt-2 text-sm leading-6 text-slate-500">
        {description}
      </p>

      {/* Action */}
      <div className="mt-5 flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-900">
          Open
        </span>

        <span
          className="
            text-sm
            font-semibold
            text-slate-400
            transition-transform
            duration-200
            group-hover:translate-x-1
            group-hover:text-slate-900
          "
        >
          →
        </span>
      </div>
    </Link>
  );
}

export default Dashboard;
