import api from "./api";

/**
 * Get all bookings for the authenticated user.
 */
export async function getBookings() {
  const response = await api.get("/bookings");

  return response.data;
}

/**
 * Get one booking.
 */
export async function getBookingDetails(bookingId) {
  const response = await api.get(
    `/bookings/${bookingId}`
  );

  return response.data;
}

/**
 * Cancel one booking.
 */
export async function cancelBooking(bookingId) {
  const response = await api.post(
    `/bookings/${bookingId}/cancel`
  );

  return response.data;
}