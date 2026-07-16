import React, { useState } from "react";
import { ChevronUp, Clock, Globe } from "lucide-react";

// ── Sentiment badge config ────────────────────────────────────────────────────
const SENTIMENT = {
  Positive: { label: "Positive", className: "bg-green-100 text-green-700" },
  Negative: { label: "Negative", className: "bg-red-100 text-red-700"   },
  Neutral:  { label: "Neutral",  className: "bg-gray-100 text-gray-600"  },
};

// ── Relative time helper ("2 hours ago") ─────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return null;
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (mins  < 1)   return "Just now";
    if (mins  < 60)  return `${mins}m ago`;
    if (hours < 24)  return `${hours}h ago`;
    return `${days}d ago`;
  } catch (_) {
    return null;
  }
}

// ── Split summary string into paragraphs ─────────────────────────────────────
function parseSummary(summary = "") {
  if (!summary) return [];
  return summary
    .split(/\n+/)
    .map((p) => p.replace(/\*\*/g, "").replace(/\*/g, "").trim())
    .filter(Boolean);
}

// ── NewsCard ──────────────────────────────────────────────────────────────────
const NewsCard = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // v2 API data shape: { headline, summary, category, sentiment, image_url, source_name, published_at }
  const paragraphs    = parseSummary(item.summary);
  const preview       = paragraphs.slice(0, 2);
  const extra         = paragraphs.slice(2);
  const sentiment     = SENTIMENT[item.sentiment] ?? SENTIMENT.Neutral;
  const relTime       = timeAgo(item.published_at || item.fetched_at);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden
                    transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 group">

      {/* ── Article image ────────────────────────────────────────────────── */}
      {item.image_url && (
        <div className="overflow-hidden h-48">
          <img
            src={item.image_url}
            alt={item.headline}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            onError={(e) => { e.target.parentElement.style.display = "none"; }}
          />
        </div>
      )}

      <div className="p-5">
        {/* ── Meta row: category + sentiment ───────────────────────────── */}
        <div className="flex flex-wrap gap-2 mb-3">
          <span className="px-2.5 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-semibold">
            {item.category}
          </span>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${sentiment.className}`}>
            {sentiment.label}
          </span>
        </div>

        {/* ── Headline ─────────────────────────────────────────────────── */}
        <h2 className="text-lg font-bold text-gray-900 leading-snug mb-3">
          {item.headline}
        </h2>

        {/* ── Preview paragraphs ────────────────────────────────────────── */}
        <div className="space-y-2">
          {preview.map((p, i) => (
            <p key={i} className="text-gray-600 text-sm leading-relaxed">
              {p}
            </p>
          ))}
        </div>

        {/* ── Expandable extra paragraphs ───────────────────────────────── */}
        {extra.length > 0 && (
          <div
            className={`transition-all duration-300 overflow-hidden ${
              isExpanded ? "max-h-[2000px] opacity-100 mt-2" : "max-h-0 opacity-0"
            }`}
          >
            <div className="space-y-2">
              {extra.map((p, i) => (
                <p key={i} className="text-gray-600 text-sm leading-relaxed">
                  {p}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* ── Footer: source + time + read more ────────────────────────── */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-50">
          <div className="flex items-center gap-3 text-xs text-gray-400">
            {item.source_name && (
              <span className="flex items-center gap-1">
                <Globe className="h-3 w-3" />
                {item.source_name}
              </span>
            )}
            {relTime && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {relTime}
              </span>
            )}
          </div>

          {extra.length > 0 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-1 text-blue-600 hover:text-blue-800
                         transition-colors duration-200 text-xs font-semibold"
            >
              {isExpanded ? "Show less" : "Read more"}
              <ChevronUp
                className={`h-3.5 w-3.5 transition-transform duration-200 ${
                  isExpanded ? "" : "rotate-180"
                }`}
              />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default NewsCard;
