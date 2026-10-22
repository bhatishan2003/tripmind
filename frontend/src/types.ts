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

export interface ItinerarySource {
  title: string;
  source_uri: string;
  destination?: string | null;
  category?: string | null;
  snippet: string;
  score: number;
}

export interface Itinerary {
  summary: string;
  total_estimated_cost: number;
  currency: string;
  days: DayPlan[];
  sources: ItinerarySource[];
}

export interface DestinationSummary {
  destination: string;
  document_count: number;
  categories: string[];
}

export interface DestinationDocument {
  id: string;
  title: string;
  source_uri: string;
  category?: string | null;
  snippet: string;
}

export interface DestinationDetail extends DestinationSummary {
  documents: DestinationDocument[];
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

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: ChatRole;
  content: string;
  sources: ItinerarySource[];
  created_at: string;
}

export interface ChatConversation {
  id: string;
  title?: string | null;
  trip_id?: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface ChatTurn {
  conversation_id: string;
  user_message: ChatMessage;
  message: ChatMessage;
}

export interface ChatRequestPayload {
  message: string;
  conversation_id?: string | null;
  trip_id?: string | null;
  stream?: boolean;
}

export interface ChatStreamMeta {
  conversation_id: string;
  user_message: ChatMessage;
}

export interface ChatStreamDone {
  conversation_id: string;
  message: ChatMessage;
}
