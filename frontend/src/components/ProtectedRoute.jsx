import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

function ProtectedRoute() {
  const {
    loading,
    isAuthenticated,
  } = useAuth();

  // --------------------------------------------------------
  // Wait until /auth/me finishes
  // --------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">
          Loading...
        </p>
      </div>
    );
  }

  // --------------------------------------------------------
  // No valid authentication
  // --------------------------------------------------------

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // --------------------------------------------------------
  // Authenticated
  // --------------------------------------------------------

  return <Outlet />;
}

export default ProtectedRoute;