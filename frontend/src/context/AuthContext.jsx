import { createContext, useContext, useEffect, useState } from "react";

import api from "../services/api";

const AuthContext = createContext(null);

const TOKEN_KEY = "travel_agent_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    return localStorage.getItem(TOKEN_KEY);
  });

  const [user, setUser] = useState(null);

  const [loading, setLoading] = useState(Boolean(token));

  const isAuthenticated = Boolean(token && user);

  // --------------------------------------------------------
  // Fetch the currently authenticated user
  // --------------------------------------------------------

  const loadCurrentUser = async () => {
    try {
      const response = await api.get("/auth/me");

      setUser(response.data);
    } catch (error) {
      console.error("Failed to load current user:", error);

      // Token is invalid/expired.
      localStorage.removeItem(TOKEN_KEY);

      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------
  // When a token exists, validate it with the backend
  // --------------------------------------------------------

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    loadCurrentUser();
  }, [token]);

  // --------------------------------------------------------
  // Login
  // --------------------------------------------------------

  const login = (accessToken) => {
    localStorage.setItem(TOKEN_KEY, accessToken);

    setToken(accessToken);
    setLoading(true);
  };

  // --------------------------------------------------------
  // Logout
  // --------------------------------------------------------

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);

    setToken(null);
    setUser(null);
    setLoading(false);
  };

  const value = {
    token,
    user,
    loading,
    isAuthenticated,
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}