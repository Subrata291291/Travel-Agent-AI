import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import api from "../services/api";
import { useAuth } from "../context/AuthContext";
import ThemeToggle from "../components/ThemeToggle";

function Login({ register = false }) {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const path = register ? "/auth/register" : "/auth/login";
      const payload = register ? { name, email, password } : { email, password };
      const response = await api.post(path, payload);
      const accessToken = response.data.access_token;
      if (!accessToken) throw new Error("The server did not return an access token.");
      login(accessToken);
      navigate("/dashboard");
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
        (requestError.response ? "Unable to authenticate. Check your details and try again." : "Could not reach the server. Please try again shortly.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page min-h-screen flex items-center justify-center px-4 py-10">
      <div className="auth-theme-control">
        <ThemeToggle />
      </div>
      <section className="auth-card w-full max-w-md rounded-2xl p-8 shadow-lg">
        <header className="mb-8 text-center">
          <h1 className="auth-title text-3xl font-bold">Travel Agent</h1>
          <p className="auth-subtitle mt-2">
            {register ? "Create an account to start planning" : "Sign in to manage your trips"}
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-5">
          {register && (
            <div>
              <label htmlFor="name" className="auth-label mb-2 block text-sm font-medium">Full name</label>
              <input id="name" name="name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={255} className="auth-input w-full rounded-lg border px-4 py-3 outline-none" />
            </div>
          )}
          <div>
            <label htmlFor="email" className="auth-label mb-2 block text-sm font-medium">Email</label>
            <input id="email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="auth-input w-full rounded-lg border px-4 py-3 outline-none" />
          </div>
          <div>
            <label htmlFor="password" className="auth-label mb-2 block text-sm font-medium">Password</label>
            <input id="password" name="password" type="password" autoComplete={register ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} maxLength={72} className="auth-input w-full rounded-lg border px-4 py-3 outline-none" />
            {register && <p className="auth-hint mt-1 text-xs">Use at least 8 characters.</p>}
          </div>
          {error && <div role="alert" className="auth-error rounded-lg px-4 py-3 text-sm">{error}</div>}
          <button type="submit" disabled={loading} className="auth-submit w-full rounded-lg px-4 py-3 font-medium transition disabled:cursor-not-allowed disabled:opacity-60">
            {loading ? (register ? "Creating account..." : "Signing in...") : (register ? "Create account" : "Sign in")}
          </button>
        </form>

        <p className="auth-footer mt-6 text-center text-sm">
          {register ? "Already have an account? " : "New to Travel Agent? "}
          <Link className="auth-link font-medium underline" to={register ? "/login" : "/register"}>
            {register ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}

export default Login;
