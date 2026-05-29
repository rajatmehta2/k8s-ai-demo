export interface User {
  email: string;
}

export interface Session {
  token: string;
  user: User;
}

export interface Diagnosis {
  root_cause: string;
  explanation: string;
  suggested_fix: string;
  command: string;
  confidence: number;
  namespace: string;
}

export interface HistoryRecord {
  timestamp: string;
  root_cause: string;
  explanation: string;
  suggested_fix: string;
  command: string;
  namespace: string;
  confidence: number;
  status: string;
}

export interface AuthResponse {
  status: string;
  message: string;
  token?: string;
}

export interface StepMessage {
  type: "step";
  step: string;
  status: "pending" | "running" | "success" | "failed";
  detail?: string;
}

export interface ResultMessage {
  type: "result";
  diagnosis: Diagnosis;
}

export interface ErrorMessage {
  type: "error";
  message?: string;
  error?: string;
}

export type WebSocketMessage = StepMessage | ResultMessage | ErrorMessage;
