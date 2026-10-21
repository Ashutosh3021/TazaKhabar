"use client";

import { useEffect, useState, useRef } from "react";
import { Icon } from "@/components/Icon";
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
          <div className="mx-auto flex items-end gap-1" aria-hidden>
            <span className="lamp lamp--live" />
            <span className="lamp lamp--off" />
            <span className="lamp lamp--off" />
          </div>
          <p className="mono-label mt-4 text-dim-text">Loading</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-4">
      <div className="mb-8 space-y-5">
        {/* Chat history */}
        {chatHistory.map((msg, i) => (
          <div
            key={i}
            className={`flex w-full flex-col ${
              msg.sender === "user" ? "items-end" : "items-start"
            }`}
            data-reveal="up"
          >
            <div
              className={`max-w-[88%] p-4 ${
                msg.sender === "user"
                  ? "panel panel--accent border-primary/50"
                  : "panel"
              }`}
            >
              <p className="mono-label leading-relaxed text-neutral-beige">{msg.text}</p>
            </div>
            <span className="mono-label mt-2 text-dim-text">
              {msg.sender === "user" ? "USER" : "RADAR_AI"}
            </span>
          </div>
        ))}
        <div ref={chatEndRef} />

        {/* Role matches */}
        {matches.length > 0 && (
          <div className="panel panel--accent w-full overflow-hidden p-0">
            <div className="flex items-center justify-between gap-3 bg-primary px-4 py-2 text-background-dark">
              <span className="mono-label">Best role matches</span>
              <span className="mono-label">
                Profile: {profile?.has_profile ? "Active" : "Guest"}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 bg-background-dark p-5 md:grid-cols-2">
              {matches.map((match) => (
                <div key={match.role} className="flex flex-col justify-between p-4">
                  <div>
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <h4 className="display text-[17px]">{match.role}</h4>
                      <span
                        className={`mono-label shrink-0 border px-2 py-0.5 ${
                          match.match_percentage >= 80
                            ? "border-primary bg-primary text-background-dark"
                            : "border-primary text-primary"
                        }`}
                      >
                        {match.match_percentage}%
                      </span>
                    </div>
                    <p className="mono-label mb-4 text-dim-text">
                      {match.job_count} open positions
                    </p>
                    <div className="space-y-2">
                      <p className="mono-label text-dim-text">Required skills</p>
                      <div className="flex flex-wrap gap-2">
                        {match.skills.slice(0, 3).map((s) => (
                          <span key={s} className="chip !cursor-default">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn mt-5 !justify-between !py-2"
                  >
                    Analyse why
                    <Icon name="arrow_forward" className="text-[15px]" aria-hidden />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="sticky bottom-2 z-30">
        <div className="panel flex items-stretch border-primary/50 p-0">
          <label htmlFor="qa-input-mobile" className="sr-only">
            Ask Radar AI
          </label>
          <input
            id="qa-input-mobile"
            className="field flex-1 border-none bg-transparent uppercase tracking-widest"
            placeholder="Ask Radar AI"
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
            className="btn btn--primary shrink-0"
          >
            Send
            <Icon name="arrow_forward" className="text-[15px]" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
