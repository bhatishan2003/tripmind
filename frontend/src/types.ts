export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  created_at: string;
}

export interface Activity {
  time: string;
  title: string;
  description: string;
  location: string;
  category: string;
  cost_estimate: number;
}

export interface DayPlan {
  day_number: number;
  date: string;
  theme: string;
  activities: Activity[];
  meals: string[];
  notes: string;
}

export interface Itinerary {
  summary: string;
  total_estimated_cost: number;
  currency: string;
  days: DayPlan[];
}

export interface Trip {
  id: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget: string | number;
  currency: string;
  travelers: number;
  travel_style: string;
  interests: string[];
  status: string;
  itinerary?: Itinerary | null;
  created_at: string;
  updated_at: string;
}

export interface TripCreatePayload {
  destination: string;
  start_date: string;
  end_date: string;
  budget: string;
  currency: string;
  travelers: number;
  travel_style: string;
  interests: string[];
}

export type TripUpdatePayload = Partial<{
  destination: string;
  start_date: string;
  end_date: string;
  budget: string | number;
  travelers: number;
  travel_style: string;
  interests: string[];
  status: string;
}>;
