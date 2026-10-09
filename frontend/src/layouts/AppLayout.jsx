import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getUserDisplayName, getUserInitial } from "../utils/userDisplay";

function AppLayout() {
  const { user, logout } = useAuth();

  const navItems = [
    {
      label: "Dashboard",
      path: "/dashboard",
      icon: "⌂",
    },
    {
      label: "AI Travel Agent",
      path: "/chat",
      icon: "✦",
    },
    {
      label: "My Trips",
      path: "/my-trips",
      icon: "▣",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">

      {/* =====================================================
          TOP HEADER
      ====================================================== */}
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="flex h-16 items-center justify-between px-5 lg:px-8">

          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-lg text-white shadow-sm">
              ✈
            </div>

            <div>
              <h1 className="text-base font-bold tracking-tight text-slate-900">
                TravelAI
              </h1>

              <p className="text-[11px] font-medium text-slate-400">
                Smart Travel Assistant
              </p>
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">

            {/* Notification */}
            <button
              type="button"
              className="relative hidden h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-900 sm:flex"
              aria-label="Notifications"
            >
              <span className="text-lg">♢</span>

              <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-blue-500 ring-2 ring-white" />
            </button>

            {/* User */}
            <div className="flex items-center gap-3 border-l border-slate-200 pl-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-semibold text-slate-800">
                  {getUserDisplayName(user)}
                </p>

                <p className="text-xs capitalize text-slate-400">
                  {user?.role || "user"}
                </p>
              </div>

              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-slate-800 to-slate-950 text-sm font-bold text-white shadow-sm">
                {getUserInitial(user)}
              </div>
            </div>

          </div>
        </div>
      </header>

      {/* =====================================================
          APPLICATION BODY
      ====================================================== */}
      <div className="flex min-h-[calc(100vh-4rem)]">

        {/* ===================================================
            SIDEBAR
        ==================================================== */}
        <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">

          <div className="flex h-full flex-col p-4">

            {/* Workspace */}
            <div className="mb-6 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-4 text-white shadow-sm">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">
                Workspace
              </p>

              <p className="mt-1 text-sm font-semibold">
                Personal Travel
              </p>

              <p className="mt-1 text-xs text-slate-400">
                Plan, book and manage trips
              </p>
            </div>

            {/* Navigation */}
            <nav className="space-y-1">

              <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400">
                Menu
              </p>

              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    [
                      "group flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all duration-200",
                      isActive
                        ? "bg-slate-900 text-white shadow-sm"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                    ].join(" ")
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={[
                          "flex h-8 w-8 items-center justify-center rounded-lg text-base transition",
                          isActive
                            ? "bg-white/10 text-white"
                            : "bg-slate-100 text-slate-500 group-hover:bg-white",
                        ].join(" ")}
                      >
                        {item.icon}
                      </span>

                      <span>{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}

            </nav>

            {/* Bottom section */}
            <div className="mt-auto space-y-1 border-t border-slate-100 pt-4">

              <button
                type="button"
                className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100">
                  ⚙
                </span>

                Settings
              </button>

              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-red-500 transition hover:bg-red-50"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-50">
                  ↪
                </span>

                Logout
              </button>

            </div>

          </div>
        </aside>

        {/* ===================================================
            MAIN CONTENT
        ==================================================== */}
        <main className="min-w-0 flex-1">

          {/* Mobile navigation */}
          <div className="border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
            <div className="flex gap-2 overflow-x-auto">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    [
                      "whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium",
                      isActive
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600",
                    ].join(" ")
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>

          <div className="mx-auto w-full max-w-[1500px] p-5 sm:p-6 lg:p-8">
            <Outlet />
          </div>

        </main>

      </div>
    </div>
  );
}

export default AppLayout;
