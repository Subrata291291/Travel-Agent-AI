export function getUserDisplayName(user) {
  return user?.name?.trim() || user?.email?.trim() || "Traveller";
}

export function getUserInitial(user) {
  return getUserDisplayName(user).charAt(0).toUpperCase() || "T";
}
