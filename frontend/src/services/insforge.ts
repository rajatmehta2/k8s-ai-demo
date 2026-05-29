import axios from "axios";
import { Session, HistoryRecord, AuthResponse, WebSocketMessage } from "../types/insforge";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/**
 * InsForge Client SDK Emulator
 */
export const insforge = {
  auth: {
    /**
     * Registers a new user.
     */
    signUp: async (email: string, password: string): Promise<{ data: AuthResponse | null; error: string | null }> => {
      try {
        const response = await axios.post<AuthResponse>(`${API_BASE_URL}/api/auth/register`, {
          email,
          password,
        });
        return { data: response.data, error: null };
      } catch (error: unknown) {
        console.error("Sign up failed:", error);
        if (axios.isAxiosError(error)) {
          return {
            data: null,
            error: error.response?.data?.detail || "Registration failed. Please try again.",
          };
        }
        return { data: null, error: "Registration failed. Please try again." };
      }
    },

    /**
     * Signs in a user and stores the session token.
     */
    signIn: async (email: string, password: string): Promise<{ data: AuthResponse | null; error: string | null }> => {
      try {
        const response = await axios.post<AuthResponse>(`${API_BASE_URL}/api/auth/login`, {
          email,
          password,
        });
        const token = response.data?.token;
        if (token) {
          localStorage.setItem("insforge_token", token);
          localStorage.setItem("insforge_user_email", email);
        }
        return { data: response.data, error: null };
      } catch (error: unknown) {
        console.error("Sign in failed:", error);
        if (axios.isAxiosError(error)) {
          return {
            data: null,
            error: error.response?.data?.detail || "Invalid email or password.",
          };
        }
        return { data: null, error: "Invalid email or password." };
      }
    },

    /**
     * Signs out the user and clears local storage.
     */
    signOut: (): void => {
      localStorage.removeItem("insforge_token");
      localStorage.removeItem("insforge_user_email");
    },

    /**
     * Retrieves the current session details.
     */
    getSession: (): Session | null => {
      if (typeof window === "undefined") return null;
      const token = localStorage.getItem("insforge_token");
      const email = localStorage.getItem("insforge_user_email");
      if (!token || !email) return null;
      return { token, user: { email } };
    },

    /**
     * Retrieves the active raw JWT token.
     */
    getToken: (): string | null => {
      if (typeof window === "undefined") return null;
      return localStorage.getItem("insforge_token");
    },
  },

  history: {
    /**
     * Fetches the recent investigations history list.
     */
    getRecent: async (): Promise<{ data: HistoryRecord[]; error: string | null }> => {
      try {
        const token = insforge.auth.getToken();
        if (!token) throw new Error("No active session found.");

        const response = await axios.get<{ status: string; history: HistoryRecord[] }>(
          `${API_BASE_URL}/api/investigations/history`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        return { data: response.data?.history || [], error: null };
      } catch (error: unknown) {
        console.error("Failed to fetch history:", error);
        if (axios.isAxiosError(error)) {
          return {
            data: [],
            error: error.response?.data?.detail || "Failed to load investigation history.",
          };
        }
        return { data: [], error: "Failed to load investigation history." };
      }
    },
  },

  realtime: {
    /**
     * Connects to the real-time investigation pipeline via WebSockets.
     */
    connectInvestigation: (
      onMessage: (msg: WebSocketMessage) => void,
      onError: (err: string) => void,
      onClose: () => void,
      context?: string
    ): WebSocket | null => {
      try {
        const token = insforge.auth.getToken();
        if (!token) {
          onError("Authentication token is missing.");
          return null;
        }

        // Convert HTTP url to WS url
        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const rawHost = API_BASE_URL.replace(/^https?:\/\//, "");
        const wsUrl = `${wsProtocol}//${rawHost}/api/investigate/ws`;

        console.log(`Connecting to WebSocket: ${wsUrl}...`);
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
          console.log("WebSocket connection established. Sending credentials...");
          // Send the token for authentication as first message
          socket.send(JSON.stringify({ token, context }));
        };

        socket.onmessage = (event) => {
          try {
            const data: WebSocketMessage = JSON.parse(event.data);
            onMessage(data);
          } catch (e) {
            console.error("Failed to parse WebSocket message:", e);
          }
        };

        socket.onerror = () => {
          console.error("WebSocket error");
          onError("WebSocket error occurred.");
        };

        socket.onclose = (event) => {
          console.log(`WebSocket closed: Code ${event.code}, Reason: ${event.reason}`);
          onClose();
        };

        return socket;
      } catch (e: unknown) {
        console.error("Error creating WebSocket connection:", e);
        const errMessage = e instanceof Error ? e.message : "Failed to initiate live connection.";
        onError(errMessage);
        return null;
      }
    },
  },
};
