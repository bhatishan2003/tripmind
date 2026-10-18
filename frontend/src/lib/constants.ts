export const TRAVEL_STYLES = [
  "relaxed",
  "balanced",
  "adventure",
  "luxury",
  "budget",
  "family",
] as const;

export const INTEREST_CHOICES = [
  "culture",
  "food",
  "nature",
  "nightlife",
  "history",
  "adventure",
  "shopping",
  "beaches",
  "museums",
  "music",
] as const;

export const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD"] as const;

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const GENERATION_STEPS = [
  "Understanding your constraints…",
  "Scouting destinations and neighborhoods…",
  "Balancing the budget across activities…",
  "Sequencing each day for a smooth flow…",
  "Polishing the final itinerary…",
];
