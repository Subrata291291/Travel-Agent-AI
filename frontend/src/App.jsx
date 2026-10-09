import { BrowserRouter, Routes, Route } from "react-router-dom";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import MyTrips from "./pages/MyTrips";
import BookingDetails from "./pages/BookingDetails";
import Settings from "./pages/Settings";

import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./layouts/AppLayout";

function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route
          path="/"
          element={<Login />}
        />

        {/* Public */}
        <Route
          path="/login"
          element={<Login />}
        />
        <Route
          path="/register"
          element={<Login register />}
        />

        {/* Protected */}
        <Route element={<ProtectedRoute />}>

          <Route element={<AppLayout />}>

            <Route
              path="/dashboard"
              element={<Dashboard />}
            />

            <Route
              path="/chat"
              element={<Chat />}
            />

            <Route
              path="/my-trips"
              element={<MyTrips />}
            />

            <Route
              path="/my-trips/:bookingId"
              element={<BookingDetails />}
            />

            <Route
              path="/settings"
              element={<Settings />}
            />

          </Route>

        </Route>

        {/* Unknown route */}
        <Route
          path="*"
          element={<Login />}
        />

      </Routes>
    </BrowserRouter>
  );
}

export default App;
