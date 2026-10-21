"use client";

import { useEffect, useState, useRef } from "react";
import { Icon } from "@/components/Icon";
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

  const [profile, setProfile] = useState<QaProfile | null>(null);
  const [matches, setMatches] = useState<RoleMatch[]>([]);
  const [marketVelocity, setMarketVelocity] = useState<MarketVelocity | null>(null);
  const [networkInfluence, setNetworkInfluence] = useState<NetworkInfluence | null>(null);
  const [actionRequired, setActionRequired] = useState<ActionRequired | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [profileData, matchesData, velocityData, influenceData, actionData] =
          await Promise.all([
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleSendMessage = async () => {
    if (!reply.trim() || sending) return;

    const userMessage = reply.trim();
    setReply("");
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto flex items-end gap-1" aria-hidden>
            <span className="lamp lamp--live" />
            <span className="lamp lamp--off" />
            <span className="lamp lamp--off" />
          </div>
          <p className="mono-label mt-4 text-dim-text">Loading profile</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {profile?.has_profile && (
        <p className="mono-data -mt-6 mb-8 text-[13px] text-primary">
          Welcome back, {profile.name || "User"} · ATS {profile.ats_score || "N/A"}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 border border-border-dark lg:grid-cols-12">
        {/* Chat section */}
        <div className="flex min-h-[600px] flex-col bg-background-dark lg:col-span-7 lg:border-r lg:border-border-dark">
          <div className="flex items-center justify-between border-b border-border-dark bg-card-dark p-4">
            <div className="flex gap-2" aria-hidden>
              <span className="lamp lamp--live" />
              <span className="lamp lamp--ok" />
              <span className="lamp lamp--off" />
            </div>
            <span className="mono-label text-dim-text">
              Session: TZ-{profile?.has_profile ? "ACTIVE" : "GUEST"}
            </span>
          </div>

          <div className="flex-grow space-y-6 overflow-y-auto p-6">
            <div className="flex flex-col gap-1">
              <span className="mono-label text-primary">[SYSTEM] Analyzer online</span>
              <span className="mono-label text-dim-text">
                Profile verified: {profile?.has_profile ? "Active" : "Guest mode"}
              </span>
            </div>

            <div className="space-y-4">
              {chatHistory.map((msg, i) => (
                <div key={i} className="flex gap-4">
                  <span className="mono-label shrink-0 text-primary">
                    {msg.sender === "bot" ? "BOT:" : "YOU:"}
                  </span>
                  <p className="mono-label leading-relaxed text-neutral-beige">{msg.text}</p>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
          </div>

          <div className="border-t border-border-dark bg-card-dark p-5">
            <label htmlFor="qa-input-desktop" className="sr-only">
              Message the career bot
            </label>
            <div className="flex items-center gap-3">
              <span className="mono-label text-primary" aria-hidden>
                &gt;
              </span>
              <input
                id="qa-input-desktop"
                className="field flex-1 border-none bg-transparent"
                placeholder="Type your response"
                type="text"
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={sending}
              />
              <button
                type="button"
                onClick={handleSendMessage}
                disabled={sending || !reply.trim()}
                aria-label="Send message"
                className="btn !px-3 !py-2 disabled:opacity-50"
              >
                <Icon name="keyboard_return" className="text-[16px]" aria-hidden />
              </button>
            </div>
          </div>
        </div>

        {/* Matches section */}
        <div className="space-y-4 bg-card-dark p-6 lg:col-span-5">
          <div className="mb-2 flex items-end justify-between gap-3">
            <h2 className="display text-[22px] uppercase">Matches</h2>
            <span className="mono-label text-primary">Live update</span>
          </div>

          {matches.length > 0 ? (
            matches.map((match) => (
              <div
                key={match.role}
                className={`panel p-5 transition-colors hover:border-primary/60 ${
                  match.locked ? "opacity-50" : ""
                }`}
              >
                <div className="mb-2 flex items-start justify-between gap-3">
                  <h3 className="display text-[17px] uppercase">{match.role}</h3>
                  <span className="mono-data text-[15px] text-primary">
                    {match.match_percentage}%
                  </span>
                </div>
                <div className="meter mb-4" aria-hidden>
                  <div className="meter__fill" style={{ width: `${match.match_percentage}%` }} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {match.skills.slice(0, 3).map((t) => (
                    <span key={t} className="chip !cursor-default">
                      {t}
                    </span>
                  ))}
                </div>
                <div className="scribe mt-4 pt-4">
                  <span className="mono-label text-primary">Why this role</span>
                  <p className="mt-2 text-[13px] leading-relaxed text-dim-text">{match.why}</p>
                  {match.locked && (
                    <p className="mono-label mt-2 text-dim-text">
                      Locked · complete profile to unlock
                    </p>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="panel p-5">
              <p className="mono-label text-dim-text">
                {profile?.has_profile
                  ? "No matching roles found. Try updating your profile."
                  : "Complete your profile to see role matches."}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Stats section */}
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="panel p-5" data-reveal="up">
          <span className="mono-label text-primary">Market velocity</span>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="display text-[clamp(1.75rem,1.4rem+2vw,2.5rem)] text-neutral-beige">
              {marketVelocity ? `+${marketVelocity.overall_velocity}%` : "--"}
            </span>
            <Icon name="trending_up" className="text-[16px] text-primary" aria-hidden />
          </div>
          <p className="mono-label mt-2 text-dim-text">
            Demand for your stack in {marketVelocity?.region || "EMEA"}
          </p>
          <div className="tick-rule mt-4 h-[6px] opacity-70" aria-hidden />
        </div>

        <div className="panel p-5" data-reveal="up">
          <span className="mono-label text-primary">Network influence</span>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="display text-[clamp(1.75rem,1.4rem+2vw,2.5rem)] text-neutral-beige">
              {networkInfluence?.percentile || "N/A"}
            </span>
          </div>
          <p className="mono-label mt-2 text-dim-text">Your technical reach index score</p>
          <div className="tick-rule mt-4 h-[6px] opacity-70" aria-hidden />
        </div>

        {actionRequired?.actions?.[0] ? (
          <Link
            href={actionRequired.actions[0].link}
            className="panel panel--accent group flex flex-col justify-between p-5 transition-colors hover:bg-primary/[0.08]"
          >
            <div>
              <span className="mono-label text-primary">Action required</span>
              <h4 className="display mt-4 text-[17px] uppercase leading-tight">
                {actionRequired.actions[0].title}
              </h4>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="mono-label text-neutral-beige">
                {actionRequired.actions[0].action_text}
              </span>
              <Icon name="arrow_forward" className="text-[18px] text-primary" aria-hidden />
            </div>
          </Link>
        ) : (
          <div className="panel p-5" data-reveal="up">
            <span className="mono-label text-primary">Action required</span>
            <p className="mt-4 text-[14px] text-dim-text">Your profile is up to date.</p>
            <div className="tick-rule mt-4 h-[6px] opacity-70" aria-hidden />
          </div>
        )}
      </div>
    </div>
  );
}
