import { useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import { getUserInitial } from "../utils/userDisplay";

function errorMessage(error) {
  return error.response?.data?.detail || "We couldn't save that change. Please try again.";
}

function Settings() {
  const { user, updateUser } = useAuth();
  const fileRef = useRef(null);
  const [name, setName] = useState(user?.name || "");
  const [photo, setPhoto] = useState(user?.profile_picture_data || null);
  const [email, setEmail] = useState(user?.email || "");
  const [emailPassword, setEmailPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState("");

  const showSuccess = (message) => {
    setError("");
    setNotice(message);
  };

  const showError = (message) => {
    setNotice("");
    setError(message);
  };

  const readPhoto = (file) => {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      showError("Choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      showError("Profile photos must be 2 MB or smaller.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPhoto(String(reader.result));
    reader.onerror = () => showError("We couldn't read that image.");
    reader.readAsDataURL(file);
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setSaving("profile");
    setError("");
    try {
      const response = await api.patch("/auth/profile", {
        name: name.trim(),
        profile_picture_data: photo,
      });
      updateUser(response.data);
      showSuccess("Profile saved.");
    } catch (requestError) {
      showError(errorMessage(requestError));
    } finally {
      setSaving("");
    }
  };

  const saveEmail = async (event) => {
    event.preventDefault();
    setSaving("email");
    setError("");
    try {
      const response = await api.patch("/auth/email", {
        new_email: email.trim(),
        current_password: emailPassword,
      });
      updateUser(response.data);
      setEmailPassword("");
      showSuccess("Email address updated.");
    } catch (requestError) {
      showError(errorMessage(requestError));
    } finally {
      setSaving("");
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      showError("The new passwords do not match.");
      return;
    }
    setSaving("password");
    setError("");
    try {
      await api.patch("/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showSuccess("Password updated.");
    } catch (requestError) {
      showError(errorMessage(requestError));
    } finally {
      setSaving("");
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-sm font-medium text-slate-500">Account</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-2 text-sm text-slate-500">Manage your profile and sign-in details.</p>
      </div>

      {(notice || error) && (
        <div role="status" className={`rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
          {error || notice}
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">Profile</h2>
        <p className="mt-1 text-sm text-slate-500">Update your display name and profile photo.</p>
        <form onSubmit={saveProfile} className="mt-6 space-y-5">
          <div className="flex items-center gap-4">
            {photo ? (
              <img src={photo} alt="Profile preview" className="h-16 w-16 rounded-full border border-slate-200 object-cover" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-900 text-xl font-semibold text-white">{getUserInitial({ name })}</div>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => fileRef.current?.click()} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Choose photo</button>
              {photo && <button type="button" onClick={() => setPhoto(null)} className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-50">Remove</button>}
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(event) => readPhoto(event.target.files?.[0])} />
              <p className="basis-full text-xs text-slate-400">JPEG, PNG, or WebP · up to 2 MB</p>
            </div>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={255} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <button disabled={saving !== ""} className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{saving === "profile" ? "Saving…" : "Save profile"}</button>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">Email address</h2>
        <p className="mt-1 text-sm text-slate-500">Confirm your current password to change the email used to sign in.</p>
        <form onSubmit={saveEmail} className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">New email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <label className="text-sm font-medium text-slate-700">Current password
            <input type="password" value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} required minLength={8} autoComplete="current-password" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <button disabled={saving !== ""} className="w-fit rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{saving === "email" ? "Updating…" : "Update email"}</button>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">Password</h2>
        <p className="mt-1 text-sm text-slate-500">Choose a new password with at least 8 characters.</p>
        <form onSubmit={savePassword} className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">Current password
            <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required minLength={8} autoComplete="current-password" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <span className="hidden sm:block" />
          <label className="text-sm font-medium text-slate-700">New password
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <label className="text-sm font-medium text-slate-700">Confirm new password
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-slate-500" />
          </label>
          <button disabled={saving !== ""} className="w-fit rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{saving === "password" ? "Updating…" : "Change password"}</button>
        </form>
      </section>
    </div>
  );
}

export default Settings;
