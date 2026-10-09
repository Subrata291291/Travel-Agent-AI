import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import api from "../services/api";
import { useAuth } from "../context/AuthContext";

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
    <main className="min-h-screen bg-gray-100 flex items-center justify-center px-4 py-10">
      <section className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <header className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-gray-900">Travel Agent</h1>
          <p className="mt-2 text-gray-500">
            {register ? "Create an account to start planning" : "Sign in to manage your trips"}
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-5">
          {register && (
            <div>
              <label htmlFor="name" className="mb-2 block text-sm font-medium text-gray-700">Full name</label>
              <input id="name" name="name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={255} className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-gray-900" />
            </div>
          )}
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-medium text-gray-700">Email</label>
            <input id="email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-gray-900" />
          </div>
          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-medium text-gray-700">Password</label>
            <input id="password" name="password" type="password" autoComplete={register ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} maxLength={72} className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-gray-900" />
            {register && <p className="mt-1 text-xs text-gray-500">Use at least 8 characters.</p>}
          </div>
          {error && <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          <button type="submit" disabled={loading} className="w-full rounded-lg bg-gray-900 px-4 py-3 font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60">
            {loading ? (register ? "Creating account..." : "Signing in...") : (register ? "Create account" : "Sign in")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          {register ? "Already have an account? " : "New to Travel Agent? "}
          <Link className="font-medium text-gray-900 underline" to={register ? "/login" : "/register"}>
            {register ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}

export default Login;
