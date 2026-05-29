"use client";

import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { insforge } from "../services/insforge";
import { Session, Diagnosis, HistoryRecord, WebSocketMessage } from "../types/insforge";

export default function Home() {
  // Authentication & Session State
  const [session, setSession] = useState<Session | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authSuccess, setAuthSuccess] = useState("");

  // Investigation & Realtime State
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [activeStep, setActiveStep] = useState("");
  const [stepStates, setStepStates] = useState<Record<string, "pending" | "running" | "success" | "failed">>({});
  const [investigationResult, setInvestigationResult] = useState<Diagnosis | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  
  // Telemetry & History State
  const [healthStatus, setHealthStatus] = useState<string>("checking");
  const [historyList, setHistoryList] = useState<HistoryRecord[]>([]);
  const [selectedHistory, setSelectedHistory] = useState<HistoryRecord | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Cluster Contexts State
  const [contexts, setContexts] = useState<string[]>([]);
  const [selectedContext, setSelectedContext] = useState<string>("");
  const [isContextsLoading, setIsContextsLoading] = useState(false);

  // Fetch Available contexts
  const fetchContexts = useCallback(async (token: string) => {
    setIsContextsLoading(true);
    try {
      const response = await axios.get(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/kubernetes/contexts`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (response.data?.status === "success") {
        setContexts(response.data.contexts || []);
        setSelectedContext(response.data.current || response.data.contexts?.[0] || "");
      }
    } catch (err) {
      console.error("Failed to fetch Kubernetes contexts:", err);
    } finally {
      setIsContextsLoading(false);
    }
  }, []);

  const steps = [
    "Checking Pods",
    "Reading Logs",
    "Analyzing Events",
    "Inspecting Deployments",
    "Checking Networking",
    "AI Reasoning",
    "Root Cause Found"
  ];

  // Fetch Recent Investigations from InsForge
  const fetchHistory = useCallback(async () => {
    const { data, error } = await insforge.history.getRecent();
    if (!error) {
      setHistoryList(data);
    }
  }, []);

  // Fetch backend health status & load session on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await axios.get(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/health`
        );
        if (response.data?.status === "healthy") {
          setHealthStatus("healthy");
        } else {
          setHealthStatus("degraded");
        }
      } catch (error) {
        console.error("Failed to connect to backend:", error);
        setHealthStatus("offline");
      }
    };

    checkHealth();
    
    // Load InsForge session
    const activeSession = insforge.auth.getSession();
    if (activeSession) {
      setSession(activeSession);
      fetchHistory();
      fetchContexts(activeSession.token);
    }
  }, [fetchHistory, fetchContexts]);

  // Handle Authentication
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setAuthSuccess("");

    if (!email || !password) {
      setAuthError("Email and password are required.");
      return;
    }

    if (authMode === "signup") {
      const { error } = await insforge.auth.signUp(email, password);
      if (error) {
        setAuthError(error);
      } else {
        setAuthSuccess("Account created successfully! Please sign in.");
        setAuthMode("login");
        setPassword("");
      }
    } else {
      const { error } = await insforge.auth.signIn(email, password);
      if (error) {
        setAuthError(error);
      } else {
        const activeSession = insforge.auth.getSession();
        setSession(activeSession);
        // Clear forms
        setEmail("");
        setPassword("");
        // Load user history
        fetchHistory();
        if (activeSession) {
          fetchContexts(activeSession.token);
        }
      }
    }
  };

  // Sign out handler
  const handleSignOut = () => {
    insforge.auth.signOut();
    setSession(null);
    setHistoryList([]);
    setInvestigationResult(null);
    setSelectedHistory(null);
  };

  // Trigger Investigation via InsForge WebSockets
  const startInvestigation = () => {
    setIsInvestigating(true);
    setInvestigationResult(null);
    setSelectedHistory(null);
    setErrorMessage("");
    setCurrentStepIndex(0);
    setActiveStep(steps[0]);

    // Initialize all steps to pending
    const initialStates: Record<string, "pending" | "running" | "success" | "failed"> = {};
    steps.forEach((step) => {
      initialStates[step] = "pending";
    });
    setStepStates(initialStates);

    // Open WebSocket channel with the target context
    insforge.realtime.connectInvestigation(
      (message: WebSocketMessage) => {
        // Message Handler
        if (message.type === "step") {
          const { step, status } = message;
          
          setStepStates((prev) => ({
            ...prev,
            [step]: status,
          }));

          if (status === "running") {
            setActiveStep(step);
            const idx = steps.indexOf(step);
            if (idx !== -1) {
              setCurrentStepIndex(idx);
            }
          }
        } else if (message.type === "result") {
          // Final diagnosis returned
          setInvestigationResult(message.diagnosis);
          setIsInvestigating(false);
          fetchHistory(); // Refresh history table
        } else if (message.type === "error") {
          setErrorMessage(message.message || message.error || "Investigation failed.");
          setIsInvestigating(false);
        }
      },
      (errorMsg: string) => {
        // Error Handler
        setErrorMessage(errorMsg || "Could not establish real-time socket channel.");
        setIsInvestigating(false);
      },
      () => {
        // Connection Closed Handler
        setIsInvestigating(false);
      },
      selectedContext
    );
  };

  // Copy command to clipboard helper
  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="relative min-h-screen flex flex-col justify-between bg-[#030712] text-gray-100 overflow-x-hidden font-sans">
      {/* Decorative Glow Orbs */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[500px] h-[500px] bg-purple-500/10 rounded-full blur-[100px] pointer-events-none" />
      
      {/* Grid Pattern Background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f29370f_1px,transparent_1px),linear-gradient(to_bottom,#1f29370f_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />

      {/* Header */}
      <header className="relative z-10 w-full max-w-6xl mx-auto px-6 py-6 flex items-center justify-between border-b border-gray-800/60 backdrop-blur-sm">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]">
            ⎈
          </div>
          <span className="font-semibold text-lg tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-gray-100 to-gray-400">
            AI KUBERNETES AGENT
          </span>
        </div>
        
        {/* Session and API Status Indicators */}
        <div className="flex items-center space-x-4">
          {session && (
            <div className="hidden md:flex items-center space-x-3 bg-gray-900/60 border border-gray-800 rounded-lg px-3.5 py-1.5 text-xs text-gray-300">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              <span>{session.user.email}</span>
            </div>
          )}

          <div className="flex items-center space-x-2 bg-gray-900/80 border border-gray-800 rounded-full px-4 py-1.5 text-xs text-gray-400">
            <span className="text-gray-500">API Status:</span>
            {healthStatus === "checking" && (
              <span className="flex items-center">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse mr-1.5" />
                Checking...
              </span>
            )}
            {healthStatus === "healthy" && (
              <span className="flex items-center text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
                Connected
              </span>
            )}
            {healthStatus === "degraded" && (
              <span className="flex items-center text-amber-500">
                <span className="w-2 h-2 rounded-full bg-amber-500 mr-1.5" />
                Degraded
              </span>
            )}
            {healthStatus === "offline" && (
              <span className="flex items-center text-rose-500">
                <span className="w-2 h-2 rounded-full bg-rose-500 mr-1.5" />
                Offline
              </span>
            )}
          </div>

          {session && (
            <button
              onClick={handleSignOut}
              className="text-xs bg-gray-800/80 hover:bg-rose-950/40 hover:text-rose-400 border border-gray-700/85 hover:border-rose-900/50 rounded-lg px-3 py-1.5 transition-all duration-200"
            >
              Sign Out
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="relative z-10 flex-1 max-w-5xl w-full mx-auto px-6 py-12 flex flex-col items-center justify-center space-y-12">
        
        {/* If user is NOT logged in: Show Auth Screen */}
        {!session ? (
          <div className="w-full max-w-md bg-gray-900/40 backdrop-blur-md border border-gray-800/80 rounded-2xl p-8 shadow-2xl shadow-indigo-500/5 relative overflow-hidden">
            {/* Inner card ambient light */}
            <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

            <div className="text-center mb-8 space-y-2">
              <div className="inline-flex w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 items-center justify-center font-bold text-xl text-white shadow-[0_0_15px_rgba(99,102,241,0.5)] mb-2">
                ⎈
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-white">
                {authMode === "login" ? "Sign In to AI Agent" : "Create Account"}
              </h2>
              <p className="text-gray-400 text-sm font-light">
                {authMode === "login"
                  ? "Access your Kubernetes troubleshooting cockpit"
                  : "Sign up to start scanning clusters with SRE AI"}
              </p>
            </div>

            <form onSubmit={handleAuthSubmit} className="space-y-5">
              {authError && (
                <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-lg p-3 text-center">
                  {authError}
                </div>
              )}
              {authSuccess && (
                <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-lg p-3 text-center">
                  {authSuccess}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs uppercase tracking-wider font-bold text-gray-400">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full bg-[#0b0f19] border border-gray-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-sm text-gray-200 outline-none transition-all duration-200"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs uppercase tracking-wider font-bold text-gray-400">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[#0b0f19] border border-gray-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-sm text-gray-200 outline-none transition-all duration-200"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg text-white font-medium text-sm shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all duration-200 transform active:translate-y-0.5"
              >
                {authMode === "login" ? "Sign In" : "Sign Up"}
              </button>
            </form>

            <div className="mt-6 text-center text-xs text-gray-500">
              {authMode === "login" ? (
                <p>
                  New to the platform?{" "}
                  <span
                    onClick={() => {
                      setAuthMode("signup");
                      setAuthError("");
                    }}
                    className="text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer transition-colors"
                  >
                    Create an account
                  </span>
                </p>
              ) : (
                <p>
                  Already have an account?{" "}
                  <span
                    onClick={() => {
                      setAuthMode("login");
                      setAuthError("");
                    }}
                    className="text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer transition-colors"
                  >
                    Sign in here
                  </span>
                </p>
              )}
            </div>
          </div>
        ) : (
          /* If user IS logged in: Show Active SRE Dashboard */
          <div className="w-full space-y-12">
            
            {/* Title Block */}
            <div className="text-center space-y-3">
              <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-500">
                AI Kubernetes Agent
              </h1>
              <p className="text-gray-400 text-lg font-light max-w-xl mx-auto">
                Troubleshoot cluster failures, analyze logs & events, and generate immediate suggested fixes with SRE reasoning.
              </p>
            </div>

            {/* Central Console */}
            <div className="w-full bg-gray-900/40 backdrop-blur-md border border-gray-800/80 rounded-2xl p-8 shadow-2xl shadow-indigo-500/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

              {/* Ready State */}
              {!isInvestigating && !investigationResult && !selectedHistory && !errorMessage && (
                <div className="flex flex-col items-center py-12 space-y-8">
                  {/* Ready Icon */}
                  <div className="relative flex items-center justify-center w-24 h-24 rounded-full bg-indigo-500/5 border border-indigo-500/20 shadow-[0_0_30px_rgba(99,102,241,0.1)]">
                    <span className="text-4xl text-indigo-400 animate-pulse">⎈</span>
                    <span className="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-gray-900 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                  </div>

                  {/* Cluster Context Selector */}
                  <div className="w-full max-w-md bg-gray-950/40 border border-gray-800/80 rounded-xl p-5 space-y-3.5 relative overflow-hidden backdrop-blur-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center space-x-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
                        <span>Select Target Cluster Context</span>
                      </span>
                      {isContextsLoading && <span className="text-[10px] text-indigo-400 animate-pulse">Scanning kubeconfig...</span>}
                    </div>
                    {contexts.length === 0 ? (
                      <div className="text-xs text-rose-400 bg-rose-950/20 border border-rose-900/30 rounded-lg p-3 text-center leading-relaxed">
                        No Kubernetes contexts detected in kubeconfig.<br/>
                        <span className="text-gray-500 text-[10px]">Please verify your local cluster is running.</span>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-2.5">
                        {contexts.map((ctx) => {
                          const isActive = selectedContext === ctx;
                          return (
                            <button
                              key={ctx}
                              onClick={() => setSelectedContext(ctx)}
                              className={`px-4 py-2.5 rounded-lg text-xs font-medium border text-center transition-all duration-200 ${
                                isActive
                                  ? "bg-gradient-to-r from-indigo-950/60 to-purple-950/60 border-indigo-500/80 text-indigo-200 shadow-[0_0_12px_rgba(99,102,241,0.15)]"
                                  : "bg-[#0b0f19] border-gray-800 hover:border-gray-700 text-gray-400 hover:text-gray-200"
                              }`}
                            >
                              <div className="flex items-center justify-center space-x-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-indigo-400 shadow-[0_0_6px_rgba(99,102,241,0.8)]" : "bg-gray-600"}`} />
                                <span className="truncate">{ctx}</span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Main Trigger Button */}
                  <button
                    onClick={startInvestigation}
                    disabled={!selectedContext}
                    className={`group relative px-10 py-4.5 rounded-xl text-white font-medium tracking-wide shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all duration-300 transform hover:-translate-y-0.5 active:translate-y-0 ${
                      !selectedContext ? "opacity-50 cursor-not-allowed animate-pulse" : "bg-gradient-to-r from-indigo-600 to-purple-600 hover:shadow-[0_0_30px_rgba(99,102,241,0.5)]"
                    }`}
                  >
                    <span className="absolute inset-0 w-full h-full rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <span className="relative flex items-center space-x-2">
                      <span className="font-semibold tracking-wider">Investigate Cluster</span>
                      <span className="transition-transform group-hover:translate-x-1">→</span>
                    </span>
                  </button>

                  <div className="flex items-center space-x-2 text-sm text-gray-400">
                    <span>System Status:</span>
                    <span className="flex items-center font-medium text-emerald-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-ping" />
                      Ready for SRE Auditing
                    </span>
                  </div>
                </div>
              )}

              {/* WebSocket Real-Time Loader View */}
              {isInvestigating && (
                <div className="py-8 flex flex-col items-center space-y-8">
                  {/* Orbiting Spinner */}
                  <div className="relative w-16 h-16 flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full border-4 border-indigo-500/10 border-t-indigo-500 animate-spin" />
                    <span className="text-xl text-indigo-400">⎈</span>
                  </div>

                  {/* Active Step status description */}
                  <div className="text-center space-y-2">
                    <p className="text-indigo-400 text-xs font-bold tracking-wider uppercase animate-pulse">
                      Investigating Kubernetes Cluster...
                    </p>
                    <h3 className="text-lg font-medium text-gray-200">
                      Running: {activeStep}...
                    </h3>
                  </div>

                  {/* Progressive indicator bar */}
                  <div className="w-full max-w-md bg-gray-800/40 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full transition-all duration-500"
                      style={{ width: `${((currentStepIndex + 1) / steps.length) * 100}%` }}
                    />
                  </div>

                  {/* Interactive checklist logs */}
                  <div className="w-full max-w-sm space-y-2.5 text-sm text-gray-400">
                    {steps.map((step, idx) => {
                      const state = stepStates[step];
                      return (
                        <div key={idx} className="flex items-center justify-between border-b border-gray-850/40 pb-1.5">
                          <div className="flex items-center space-x-3">
                            {state === "success" && (
                              <span className="text-emerald-400 font-bold">✓</span>
                            )}
                            {state === "running" && (
                              <span className="text-indigo-400 animate-pulse font-bold">●</span>
                            )}
                            {state === "failed" && (
                              <span className="text-rose-500 font-bold">✗</span>
                            )}
                            {state === "pending" && (
                              <span className="text-gray-700">•</span>
                            )}
                            <span className={state === "running" ? "text-gray-200 font-medium" : state === "success" ? "text-gray-500 line-through" : "text-gray-500"}>
                              {step}
                            </span>
                          </div>

                          <div>
                            {state === "success" && (
                              <span className="text-[10px] uppercase font-bold text-emerald-500/80 px-2 py-0.5 bg-emerald-950/20 border border-emerald-900/30 rounded">Done</span>
                            )}
                            {state === "running" && (
                              <span className="text-[10px] uppercase font-bold text-indigo-400 px-2 py-0.5 bg-indigo-950/20 border border-indigo-900/30 rounded animate-pulse">Running</span>
                            )}
                            {state === "pending" && (
                              <span className="text-[10px] uppercase font-bold text-gray-600">Queued</span>
                            )}
                            {state === "failed" && (
                              <span className="text-[10px] uppercase font-bold text-rose-500 bg-rose-950/20 border border-rose-900/30 rounded">Failed</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Error State */}
              {errorMessage && !isInvestigating && (
                <div className="flex flex-col items-center py-8 space-y-6">
                  <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 font-bold text-xl">
                    !
                  </div>
                  <div className="text-center space-y-2 max-w-md">
                    <h3 className="text-lg font-bold text-gray-200">Investigation Interrupted</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">{errorMessage}</p>
                  </div>
                  <button
                    onClick={startInvestigation}
                    className="px-6 py-2.5 bg-rose-950/20 hover:bg-rose-950/40 border border-rose-900/50 rounded-lg text-sm text-rose-300 font-medium transition-all"
                  >
                    Retry Audit
                  </button>
                </div>
              )}

              {/* Diagnosis Report Details (Real WebSocket results or Selected History item) */}
              {(investigationResult || selectedHistory) && !isInvestigating && (
                <div className="space-y-6">
                  {/* Result Header */}
                  {selectedHistory && (
                    <div className="flex items-center space-x-2 text-xs text-indigo-400 bg-indigo-950/20 border border-indigo-900/30 rounded-lg px-3 py-1.5 w-fit">
                      <span>Viewing History Record from {selectedHistory.timestamp}</span>
                    </div>
                  )}

                  {(() => {
                    const result = investigationResult || selectedHistory;
                    if (!result) return null;
                    const isHealthy = result.root_cause === "No critical issues detected";
                    return (
                      <>
                        {/* Diagnostic Header */}
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-gray-800/80 pb-5 gap-4">
                          <div className="flex items-start space-x-3">
                            <div className={`mt-1 px-2.5 py-1 text-xs font-bold uppercase rounded tracking-wide border ${
                              isHealthy 
                                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" 
                                : "bg-rose-500/10 border-rose-500/20 text-rose-400"
                            }`}>
                              {isHealthy ? "Verified Operational" : "Issue Detected"}
                            </div>
                            <div>
                              <h2 className={`text-xl font-bold flex items-center ${isHealthy ? "text-emerald-400" : "text-gray-100"}`}>
                                {isHealthy ? "No critical Kubernetes issues detected." : result.root_cause}
                              </h2>
                              <p className="text-sm text-gray-400 font-mono mt-0.5">
                                Namespace: {result.namespace} | Status: {isHealthy ? "Healthy" : "Completed"}
                              </p>
                            </div>
                          </div>
                          
                          {/* Confidence Meter */}
                          <div className="bg-gray-850/60 border border-gray-700/50 rounded-lg px-4 py-2.5 flex items-center space-x-3 self-start md:self-auto shadow-sm">
                            <div className="text-right">
                              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Confidence</p>
                              <p className={`text-sm font-bold ${isHealthy ? "text-emerald-400" : "text-emerald-400"}`}>{result.confidence}%</p>
                            </div>
                            <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs ${
                              isHealthy 
                                ? "bg-emerald-500/5 border border-emerald-500/20 text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)]" 
                                : "bg-indigo-500/5 border border-indigo-500/20 text-indigo-400"
                            }`}>
                              {isHealthy ? "SRE" : "AI"}
                            </div>
                          </div>
                        </div>

                        {/* Diagnostic Cards */}
                        <div className="space-y-5">
                          <div className="space-y-1.5">
                            <h4 className={`text-xs uppercase font-extrabold tracking-wider ${isHealthy ? "text-emerald-400" : "text-indigo-400"}`}>
                              {isHealthy ? "SRE Assessment Summary" : "Diagnosis Details"}
                            </h4>
                            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                              {isHealthy ? "Cluster appears healthy." : result.explanation}
                            </p>
                          </div>

                          <div className="space-y-1.5 pt-4 border-t border-gray-850/40">
                            <h4 className={`text-xs uppercase font-extrabold tracking-wider ${isHealthy ? "text-emerald-400" : "text-purple-400"}`}>
                              {isHealthy ? "Verification Commands" : "Suggested Action Plan"}
                            </h4>
                            <p className="text-gray-300 text-sm leading-relaxed">
                              {result.suggested_fix}
                            </p>
                            
                            {/* Copyable code snippet */}
                            {result.command && (
                              <div className="relative group mt-3">
                                <pre className={`bg-[#0b0f19] border border-gray-800/80 rounded-lg p-4.5 font-mono text-xs overflow-x-auto select-all leading-normal ${
                                  isHealthy ? "text-emerald-300" : "text-indigo-300"
                                }`}>
                                  {result.command}
                                </pre>
                                <button
                                  onClick={() => copyToClipboard(result.command, 999)}
                                  className="absolute right-3 top-3 px-3 py-1 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded text-[10px] text-gray-300 font-medium cursor-pointer transition-colors"
                                >
                                  {copiedIndex === 999 ? "Copied!" : "Copy"}
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Reset / Actions footer */}
                        <div className="flex justify-between items-center pt-5 border-t border-gray-800/60 mt-4">
                          <div className="text-xs text-gray-500">
                            Persistent records are managed via InsForge BaaS
                          </div>
                          
                          <div className="flex space-x-3">
                            {(selectedHistory || investigationResult) && (
                              <button
                                onClick={() => {
                                  setInvestigationResult(null);
                                  setSelectedHistory(null);
                                  setErrorMessage("");
                                }}
                                className="px-5 py-2 bg-gray-800/50 hover:bg-gray-700/80 border border-gray-700/50 rounded-lg text-xs text-gray-300 font-medium transition-all duration-200"
                              >
                                Close Report
                              </button>
                            )}

                            <button
                              onClick={startInvestigation}
                              className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg text-xs text-white font-medium shadow-sm transition-all duration-200"
                            >
                              Scan Cluster Again
                            </button>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Previous Investigations Section (History Log) */}
            <div className="w-full space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <h3 className="text-lg font-bold text-gray-200 flex items-center space-x-2">
                  <span>Previous Investigations</span>
                  <span className="text-xs font-normal text-gray-500 bg-gray-900 border border-gray-850 px-2 py-0.5 rounded-full">
                    {historyList.length} logs
                  </span>
                </h3>
                
                <button
                  onClick={fetchHistory}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
                >
                  Refresh Logs
                </button>
              </div>

              {historyList.length === 0 ? (
                <div className="bg-gray-900/20 border border-gray-850 rounded-xl p-8 text-center text-sm text-gray-500">
                  No previous investigations found. Trigger a scan above to build your troubleshooting history.
                </div>
              ) : (
                <div className="bg-gray-900/30 border border-gray-800/60 rounded-xl overflow-hidden shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-gray-950/40 border-b border-gray-800 text-gray-400 uppercase tracking-wider font-bold">
                          <th className="px-5 py-3">Timestamp</th>
                          <th className="px-5 py-3">Detected Issue</th>
                          <th className="px-5 py-3">Namespace</th>
                          <th className="px-5 py-3">Confidence</th>
                          <th className="px-5 py-3">Status</th>
                          <th className="px-5 py-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-850/50">
                        {historyList.map((item, idx) => (
                          <tr 
                            key={idx} 
                            className={`hover:bg-gray-850/20 transition-all ${
                              selectedHistory && selectedHistory.timestamp === item.timestamp
                                ? "bg-indigo-950/10"
                                : ""
                            }`}
                          >
                            <td className="px-5 py-3.5 text-gray-400 font-mono">{item.timestamp}</td>
                            <td className="px-5 py-3.5 font-semibold text-gray-200">{item.root_cause}</td>
                            <td className="px-5 py-3.5 font-mono text-gray-400">{item.namespace}</td>
                            <td className="px-5 py-3.5">
                              <span className={`font-bold ${
                                item.confidence >= 80
                                  ? "text-emerald-400"
                                  : item.confidence >= 50
                                  ? "text-amber-400"
                                  : "text-rose-400"
                              }`}>
                                {item.confidence}%
                              </span>
                            </td>
                            <td className="px-5 py-3.5">
                              <span className="inline-flex items-center px-2 py-0.5 bg-emerald-950/20 border border-emerald-900/30 text-emerald-400 rounded text-[10px] font-bold uppercase">
                                {item.status}
                              </span>
                            </td>
                            <td className="px-5 py-3.5 text-right">
                              <button
                                onClick={() => {
                                  setSelectedHistory(item);
                                  setInvestigationResult(null);
                                  setErrorMessage("");
                                  // Scroll slightly up to dashboard console
                                  window.scrollTo({ top: 120, behavior: "smooth" });
                                }}
                                className="text-indigo-400 hover:text-indigo-300 font-semibold hover:underline"
                              >
                                View SRE Report
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="relative z-10 w-full max-w-6xl mx-auto px-6 py-6 text-center text-xs text-gray-500 border-t border-gray-850/40 bg-[#030712]/30 backdrop-blur-sm">
        <p>AI Kubernetes Troubleshooting Agent • Protected by InsForge Enterprise Shield • Built with FastAPI, Next.js, and OpenRouter</p>
      </footer>
    </div>
  );
}
