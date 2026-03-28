"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import {
  fetchQaProfile,
  fetchRoleMatches,
  sendChatMessage,
  type QaProfile,
  type RoleMatch,
} from "@/lib/api";

interface ChatMessage {
  sender: "user" | "bot";
  text: string;
}

export default function QaCareerBotMobile() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [profile, setProfile] = useState<QaProfile | null>(null);
  const [matches, setMatches] = useState<RoleMatch[]>([]);
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [profileData, matchesData] = await Promise.all([
          fetchQaProfile(),
          fetchRoleMatches(3),
        ]);
        
        setProfile(profileData);
        setMatches(matchesData.matches);
        
        if (profileData.has_profile) {
          setChatHistory([
            {
              sender: "user",
              text: "Analyze the current job market trends. Match against my profile and highlight critical skill gaps.",
            },
            {
              sender: "bot",
              text: `Analysis complete. Based on your profile as ${profileData.roles.join(" / ")}, market data indicates strong demand.`,
            },
            {
              sender: "bot",
              text: `Your profile shows ${profileData.ats_score || 0}% compatibility with current openings.`,
            },
          ]);
        } else {
          setChatHistory([
            {
              sender: "user",
              text: "Analyze the current job market trends. Match against my profile and highlight critical skill gaps.",
            },
            {
              sender: "bot",
              text: "I don't have your profile data yet. Please complete onboarding and upload your resume to get personalized recommendations.",
            },
          ]);
        }
      } catch (err) {
        console.error("Failed to load Q&A data:", err);
      } finally {
        setLoading(false);
      }
    }
    
    loadData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleSend = async () => {
    if (!prompt.trim() || sending) return;
    
    const userMessage = prompt.trim();
    setPrompt("");
    setSending(true);
    
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
    if (e.key === "Enter") {
      handleSend();
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="mt-4 font-mono text-xs text-dim-text">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="selection:bg-primary selection:text-background-dark">
      <header className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between border-b border-border-dark bg-background-dark px-6 py-4">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="text-primary"
            aria-label="Go back"
          >
            <span className="material-symbols-outlined">arrow_back</span>
          </button>
          <h1 className="mono-label text-lg uppercase text-neutral-beige">
            TazaKhabar
          </h1>
        </div>
        <button type="button" className="text-primary" aria-label="Search">
          <span className="material-symbols-outlined">search</span>
        </button>
      </header>

      <main className="mx-auto max-w-4xl px-4 pb-40 pt-20 md:px-8">
        <div className="mb-12 border-l-4 border-primary py-2 pl-6">
          <h2 className="font-serif text-6xl font-black leading-none md:text-8xl">
            Radar <span className="text-primary">AI.</span>
          </h2>
          <p className="mono-label mt-4 text-xs tracking-[0.2rem] text-dim-text">
            Terminal v4.02 // Intelligence Engine
          </p>
        </div>

        <div className="mb-12 space-y-8">
          {/* Chat History */}
          {chatHistory.map((msg, i) => (
            <div
              key={i}
              className={`flex w-full ${msg.sender === "user" ? "flex-col items-end" : "flex-col items-start"}`}
            >
              <div
                className={`max-w-[85%] border p-5 ${
                  msg.sender === "user"
                    ? "border-primary bg-selected-bg"
                    : "border-border-dark bg-background-dark"
                }`}
              >
                <p className="font-mono text-sm leading-relaxed text-neutral-beige">
                  {msg.text}
                </p>
              </div>
              <span className="mono-label mt-2 text-[10px] text-dim-text">
                {msg.sender === "user" ? "USER" : "RADAR_AI"} // {new Date().toLocaleTimeString()}
              </span>
            </div>
          ))}
          <div ref={chatEndRef} />

          {/* Role Matches */}
          {matches.length > 0 && (
            <div className="w-full overflow-hidden border-2 border-primary p-0">
              <div className="flex items-center justify-between bg-primary px-4 py-2 text-background-dark">
                <span className="mono-label text-xs tracking-widest">
                  BEST ROLE MATCHES
                </span>
                <span className="mono-label text-[10px] uppercase">
                  Profile: {profile?.has_profile ? "Active" : "Guest"}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-6 bg-background-dark p-6 md:grid-cols-2">
                {matches.map((match) => (
                  <div
                    key={match.role}
                    className="flex flex-col justify-between border border-border-dark p-4"
                  >
                    <div>
                      <div className="mb-2 flex items-start justify-between">
                        <h4 className="font-serif text-xl font-bold text-neutral-beige">
                          {match.role}
                        </h4>
                        <span
                          className={`px-2 py-0.5 font-mono text-xs font-bold ${
                            match.match_percentage >= 80
                              ? "bg-primary text-background-dark"
                              : "border border-primary text-primary"
                          }`}
                        >
                          {match.match_percentage}% MATCH
                        </span>
                      </div>
                      <p className="mono-label mb-4 text-[10px] uppercase text-dim-text">
                        {match.job_count} open positions
                      </p>
                      <div className="space-y-2">
                        <p className="mono-label text-[10px] uppercase tracking-tighter text-dim-text">
                          Required Skills:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {match.skills.slice(0, 3).map((s) => (
                            <span
                              key={s}
                              className="border border-border-dark px-2 py-1 font-mono text-[9px] uppercase text-neutral-beige"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="mt-6 p-2 text-left font-mono text-xs font-bold text-primary transition-none hover:bg-primary hover:text-background-dark"
                    >
                      ANALYSE WHY →
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      <div className="fixed bottom-16 left-0 right-0 z-40 bg-gradient-to-t from-background-dark via-background-dark to-transparent px-4 pb-4 pt-12 md:px-8">
        <div className="mx-auto flex max-w-4xl items-stretch border-2 border-primary bg-black">
          <input
            className="flex-grow border-none bg-transparent px-6 py-4 font-mono text-sm uppercase tracking-widest text-neutral-beige placeholder:text-dim-text focus:ring-0"
            placeholder="Ask Radar AI..."
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={sending}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={sending || !prompt.trim()}
            className="bg-primary px-8 py-4 font-mono text-sm font-bold text-background-dark transition-none hover:invert disabled:opacity-50"
          >
            SEND →
          </button>
        </div>
      </div>
    </div>
  );
}
