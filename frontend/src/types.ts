export type Topic = {
  id: number;
  name: string;
  code: string;
  subject_id?: number;
};
export type Subject = {
  id: number;
  slug: string;
  name: string;
  active: boolean;
  topics: Topic[];
};
export type MentorProfile = {
  bio: string;
  price: number;
  topic_ids: number[];
  formats: string[];
  verified: boolean;
  active: boolean;
  suspended: boolean;
};
export type User = {
  id: number;
  name: string;
  email: string | null;
  campus: string;
  course: number;
  languages: string[];
  interests: number[];
  registered: boolean;
  is_admin: boolean;
  mentor: MentorProfile | null;
};
export type Slot = {
  id: number;
  mentor_id: number;
  starts_at: number;
  ends_at: number;
  enabled: boolean;
  series_id?: string | null;
  capacity?: number;
  taken?: number | null;
  price?: number | null;
  topic_id?: number | null;
  min_participants?: number | null;
  format?: string | null;
  students?: string[];
  state?: string;
  booking_id?: string | null;
  student?: string | null;
};
export type Mentor = MentorProfile & {
  id: number;
  name: string;
  course: number;
  campus: string;
  languages: string[];
  rating: number | null;
  review_count: number;
  rating_score?: number | null;
  is_favorite?: boolean;
  slots: Slot[];
  reasons: string[];
  /** Mentor cards carry only id/name/subject of each topic (no code). */
  topics: { id: number; name: string; subject_id: number }[];
  reviews?:
    | {
        rating: number;
        comment: string;
        student: string;
        created_at: number;
      }[]
    | null;
};
export type Booking = {
  id: string;
  student_id: number;
  student_name: string;
  mentor_id: number;
  mentor_name: string;
  topic_id: number;
  topic: string;
  subject_id: number;
  slot: Slot;
  price: number;
  status: string;
  status_label: string;
  description: string;
  deadline: number;
  format: string;
  language: string;
  created_at: number;
  expires_at: number;
  meeting_url: string;
  meeting_place: string;
  materials: string;
  mentor_completed_at: number | null;
  unread_messages?: number;
  group?: { capacity: number; taken: number; participants: string[] } | null;
  reschedule?: {
    id: number;
    proposed_slot: Slot;
    requested_by: number;
    expires_at: number;
  } | null;
  notes?: string;
  review: {
    rating: number;
    comment: string;
  } | null;
  quizzes: Record<
    string,
    {
      id: string;
      score: number | null;
      total: number;
    }
  >;
  receipt?: {
    id: string;
    amount: number;
    commission: number;
    mentor_amount: number;
  } | null;
};
export type Plant = {
  subject_id: number;
  name: string;
  slug: string;
  points: number;
  level: number;
  next_level: number | null;
};
export type Progress = {
  plants: Plant[];
  completed_sessions: number;
  successful_tests: number;
  points: number;
  achievements: {
    name: string;
    description: string;
    earned: boolean;
  }[];
};
export type Notice = {
  id: number;
  body: string;
  kind: string;
  booking_id: string | null;
  status: string;
  read: boolean;
  due_at: number;
  link?: string | null;
};
export type Waitlist = {
  id: number;
  topic: string;
  deadline: number;
  budget: number;
};
export type Config = {
  mode: 'demo' | 'site';
  timezone: string;
  payment: string;
  demo_accounts: {
    id: number;
    name: string;
    role: string;
  }[];
};
export type Quiz = {
  id: string;
  topic: string;
  stage: string;
  score: number | null;
  submitted: boolean;
  questions: {
    id: number;
    text: string;
    options: string[];
  }[];
  answers?: number[] | null;
  feedback?:
    | {
        correct: number;
        explanation: string;
        is_correct: boolean;
      }[]
    | null;
};
export type Filters = {
  topic_id: number;
  budget: number;
  earliest: number;
  deadline: number;
  language: string;
  format: string;
  /** Free-text search; empty means no text filter. */
  q: string;
  sort: 'soonest' | 'price' | 'rating';
  favorites_only: number;
};
export type Admin = {
  stats: {
    total: number;
    completed: number;
    completion_rate: number | null;
    cancelled: number;
    median_confirmation_seconds: number | null;
    repeat_students: number;
    unique_students: number;
    repeat_rate: number | null;
    topics: {
      topic: string;
      count: number;
    }[];
    definitions: Record<string, string>;
  };
  mentors: Mentor[];
  bookings: Booking[];
  catalog: Subject[];
  waitlist: {
    student: string;
    topic: string;
    deadline: number;
    budget: number;
  }[];
  delivery_issues: {
    id: number;
    status: string;
    kind: string;
  }[];
};
export type Snapshot = {
  user: User;
  catalog: Subject[];
  bookings: Booking[];
  progress: Progress;
  notifications: Notice[];
  slots: Slot[];
  waitlist: Waitlist[];
  favorites: Mentor[];
  admin: Admin | null;
};
export type Navigate = (path: string) => void;
export type Mutate = <T = unknown>(path: string, body: unknown, method?: string) => Promise<T>;
export type ChatMessage = {
  id: number;
  sender_id: number;
  sender_name: string;
  body: string;
  created_at: number;
  client_id: string;
};
export type ChatThread = {
  thread: string;
  can_write: boolean;
  messages: ChatMessage[];
  my_last_read_id: number;
  others_last_read_id: number;
};
export type ToggleFavorite = (mentorId: number, on: boolean) => Promise<unknown>;
export type SeriesResult = {
  series_id: string;
  created: Slot[];
  skipped: { starts_at: number; reason: string }[];
};
