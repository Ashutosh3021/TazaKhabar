"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  fetchQaProfile,
  fetchRoleMatches,
  fetchMarketVelocity,
  fetchNetworkInfluence,
  fetchActionRequired,
  sendChatMessage,
  type QaProfile,
  type RoleMatch,
  type MarketVelocity,
  type NetworkInfluence,
  type ActionRequired,
} from "@/lib/api";

interface ChatMessage {
  sender: "user" | "bot";
  text: string;
}

export default function QaCareerBotDesktop() {
  const [loading, setLoading] = useState(true);
  const [reply, setReply] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  
  // Data states
  const [profile, setProfile] = useState<QaProfile | null>(null);
  const [matches, setMatches] = useState<RoleMatch[]>([]);
  const [marketVelocity, setMarketVelocity] = useState<MarketVelocity | null>(null);
  const [networkInfluence, setNetworkInfluence] = useState<NetworkInfluence | null>(null);
  const [actionRequired, setActionRequired] = useState<ActionRequired | null>(null);
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load data on mount
  useEffect(() => {
    async function loadData() {
      try {
        const [profileData, matchesData, velocityData, influenceData, actionData] = await Promise.all([
          fetchQaProfile(),
          fetchRoleMatches(5),
          fetchMarketVelocity(),
          fetchNetworkInfluence(),
          fetchActionRequired(),
        ]);
        
        setProfile(profileData);
        setMatches(matchesData.matches);
        setMarketVelocity(velocityData);
        setNetworkInfluence(influenceData);
        setActionRequired(actionData);
        
        // Set initial chat message based on profile
        if (profileData.has_profile) {
          setChatHistory([
            {
              sender: "bot",
              text: `Analysis complete. Based on your profile as ${profileData.roles.join(" / ")}, I have mapped your trajectory.`,
            },
            {
              sender: "bot",
              text: `You exhibit a strong profile. I recommend focusing on ${matchesData.matches[0]?.role || "relevant roles"} based on current market trends.`,
            },
            {
              sender: "bot",
              text: "Would you like to view the specific market trends for these roles?",
            },
          ]);
        } else {
          setChatHistory([
            {
              sender: "bot",
              text: "Welcome to Career Bot! I don't have your profile yet. Please complete your onboarding and upload a resume to get personalized recommendations.",
            },
          ]);
        }
      } catch (err) {
        console.error("Failed to load Q&A data:", err);
        // Fallback to empty state
        setChatHistory([
          {
            sender: "bot",
            text: "Welcome to Career Bot! I'm having trouble loading your profile data. Please try again later.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    
    loadData();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleSendMessage = async () => {
    if (!reply.trim() || sending) return;
    
    const userMessage = reply.trim();
    setReply("");
    setSending(true);
    
    // Add user message to chat
    setChatHistory((prev) => [...prev, { sender: "user", text: userMessage }]);
    
    try {
      const response = await sendChatMessage(userMessage);
      setChatHistory((prev) => [...prev, { sender: "bot", text: response.response }]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        { sender: "bot", text: "Sorry, I couldn't process your message. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="mt-4 font-mono text-sm text-dim-text">Loading your profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative selection:bg-primary selection:text-white">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 opacity-5"
      >
        <div className="absolute right-0 top-0 h-full w-1/2 bg-gradient-to-l from-primary to-transparent" />
        <div className="absolute bottom-0 left-0 h-1/2 w-full bg-[radial-gradient(circle_at_bottom_left,_var(--tw-gradient-stops))] from-primary/20 via-transparent to-transparent" />
      </div>

      <main className="mx-auto max-w-[1440px] px-6 py-12">
        <div className="mb-16 border-l-4 border-primary pl-8">
          <h1 className="font-sans text-6xl font-black uppercase leading-none tracking-tighter text-neutral-beige md:text-8xl">
            <span>Career</span>{" "}
            <span className="font-serif italic text-primary">Bot.</span>
          </h1>
          <p className="mt-4 font-mono text-lg tracking-tight text-dim-text">
            AI-driven role optimization based on your verified profile.
          </p>
          {profile?.has_profile && (
            <p className="mt-2 font-mono text-sm text-primary">
              Welcome back, {profile.name || "User"} | ATS Score: {profile.ats_score || "N/A"}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-0 border border-neutral-border lg:grid-cols-12">
          {/* Chat Section */}
          <div className="flex min-h-[600px] flex-col border-neutral-border bg-black lg:col-span-7 lg:border-r">
            <div className="flex items-center justify-between border-b border-neutral-border bg-card-dark p-4">
              <div className="flex gap-2">
                <div className="h-3 w-3 rounded-[50%] bg-red-500" />
                <div className="h-3 w-3 rounded-[50%] bg-yellow-500" />
                <div className="h-3 w-3 rounded-[50%] bg-green-500" />
              </div>
              <span className="mono-label text-[10px] text-dim-text">
                Session: TZ-{profile?.has_profile ? "ACTIVE" : "GUEST"}
              </span>
            </div>
            
            <div className="flex-grow space-y-6 overflow-y-auto p-6 font-mono text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-primary/80">
                  [SYSTEM] INITIALIZING NEURAL ANALYZER...
                </span>
                <span className="text-dim-text">
                  Profile verified: {profile?.has_profile ? "Active" : "Guest Mode"}
                </span>
              </div>
              
              <div className="space-y-4">
                {chatHistory.map((msg, i) => (
                  <div key={i} className="flex gap-4">
                    <span className="font-bold text-primary">
                      {msg.sender === "bot" ? "BOT:" : "YOU:"}
                    </span>
                    <p className="leading-relaxed text-neutral-beige">
                      {msg.text}
                    </p>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            </div>
            
            <div className="border-t border-neutral-border bg-card-dark p-6">
              <div className="flex items-center gap-4 border border-neutral-border bg-background-dark px-4 py-3">
                <span className="font-mono text-primary">&gt;</span>
                <input
                  className="w-full border-none bg-transparent font-mono text-neutral-beige placeholder:text-dim-text/40 focus:ring-0"
                  placeholder="Type your response..."
                  type="text"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={handleKeyPress}
                  disabled={sending}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={sending || !reply.trim()}
                  className="material-symbols-outlined text-sm text-dim-text hover:text-primary disabled:opacity-50"
                >
                  keyboard_return
                </button>
              </div>
            </div>
          </div>

          {/* Matches Section */}
          <div className="space-y-8 bg-background-dark p-8 lg:col-span-5">
            <div className="mb-4 flex items-end justify-between">
              <h2 className="font-sans text-3xl font-black uppercase tracking-tighter text-neutral-beige">
                Matches
              </h2>
              <span className="mono-label mb-1 text-[10px] tracking-[0.2em] text-primary">
                REAL-TIME UPDATE
              </span>
            </div>

            {matches.length > 0 ? (
              matches.map((match, i) => (
                <div
                  key={match.role}
                  className={`group flex cursor-pointer flex-col border border-neutral-border p-0 transition-colors hover:border-primary ${
                    match.locked ? "opacity-50 grayscale" : ""
                  }`}
                >
                  <div className="border-b border-neutral-border bg-card-dark p-6 transition-all duration-200 group-hover:bg-primary">
                    <div className="mb-2 flex items-start justify-between">
                      <h3 className="font-sans text-2xl font-black uppercase tracking-tight text-white group-hover:text-white">
                        {match.role}
                      </h3>
                      <span className="font-sans text-2xl font-black text-primary group-hover:text-white">
                        {match.match_percentage}% MATCH
                      </span>
                    </div>
                    <div className="flex gap-2">
                      {match.skills.slice(0, 3).map((t) => (
                        <span
                          key={t}
                          className="mono-label border border-white/20 px-2 py-0.5 text-[10px] text-white/60 group-hover:border-white group-hover:text-white"
                        >
                          {t.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="p-6">
                    <span className="mono-label mb-2 block text-[10px] tracking-widest text-primary">
                      WHY THIS ROLE
                    </span>
                    <p className="font-sans text-sm text-dim-text">
                      {match.why}
                    </p>
                    {match.locked && (
                      <p className="mono-label mt-2 text-xs text-dim-text">
                        LOCKED — COMPLETE PROFILE TO UNLOCK
                      </p>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="border border-neutral-border bg-card-dark p-6">
                <p className="font-mono text-sm text-dim-text">
                  {profile?.has_profile
                    ? "No matching roles found. Try updating your profile."
                    : "Complete your profile to see role matches."}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Stats Section */}
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
          {/* Market Velocity */}
          <div className="border border-neutral-border bg-card-dark p-6">
            <span className="mono-label mb-2 block text-[10px] tracking-widest text-primary">
              Market Velocity
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-sans text-4xl font-black text-neutral-beige">
                {marketVelocity ? `+${marketVelocity.overall_velocity}%` : "--"}
              </span>
              <span className="material-symbols-outlined text-sm text-primary">
                trending_up
              </span>
            </div>
            <p className="mono-label mt-2 text-xs tracking-tighter text-dim-text">
              Demand for your tech stack in {marketVelocity?.region || "EMEA"}
            </p>
          </div>
          
          {/* Network Influence */}
          <div className="border border-neutral-border bg-card-dark p-6">
            <span className="mono-label mb-2 block text-[10px] tracking-widest text-primary">
              Network Influence
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-sans text-4xl font-black text-neutral-beige">
                {networkInfluence?.percentile || "N/A"}
              </span>
            </div>
            <p className="mono-label mt-2 text-xs tracking-tighter text-dim-text">
              Your technical reach index score
            </p>
          </div>
          
          {/* Action Required */}
          {actionRequired?.actions?.[0] ? (
            <Link
              href={actionRequired.actions[0].link}
              className="group flex cursor-pointer flex-col justify-between border border-primary bg-primary p-6 transition-all active:scale-95"
            >
              <div>
                <span className="mono-label mb-2 block text-[10px] tracking-widest text-white">
                  Action Required
                </span>
                <h4 className="font-sans text-xl font-black uppercase leading-tight text-white">
                  {actionRequired.actions[0].title}
                </h4>
              </div>
              <div className="mt-4 flex items-center justify-between text-white">
                <span className="font-mono text-xs">{actionRequired.actions[0].action_text}</span>
                <span className="material-symbols-outlined">arrow_forward</span>
              </div>
            </Link>
          ) : (
            <div className="border border-neutral-border bg-card-dark p-6">
              <span className="mono-label mb-2 block text-[10px] tracking-widest text-primary">
                Action Required
              </span>
              <p className="font-sans text-sm text-dim-text">
                Your profile is up to date!
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
