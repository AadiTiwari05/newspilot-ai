import React, { useState } from "react";
import { ChevronUp } from "lucide-react";

// BUG-06 fix: use correct data shape { category, title, paragraphs, image_urls }
// BUG-WARN-02 fix: removed ~60 lines of dead commented-out duplicate code
// BUG-WARN-03 fix: removed all console.log debug statements

const NewsCard = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Show first 2 paragraphs as preview, rest on expand
  const previewParagraphs = item.paragraphs?.slice(0, 2) || [];
  const extraParagraphs = item.paragraphs?.slice(2) || [];

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden transition-all duration-300 hover:shadow-xl mb-6">
      {/* Article image */}
      {item.image_urls && (
        <img
          src={item.image_urls}
          alt={item.title}
          className="w-full h-52 object-cover"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
      )}

      <div className="p-6">
        <div className="flex justify-between items-start mb-3">
          <h2 className="text-xl font-bold text-gray-800 leading-snug flex-1 mr-3">
            {item.title}
          </h2>
          <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium whitespace-nowrap">
            {item.category}
          </span>
        </div>

        {/* Preview paragraphs always visible */}
        <div className="space-y-3">
          {previewParagraphs.map((paragraph, pIndex) => (
            <p key={pIndex} className="text-gray-600 leading-relaxed text-sm">
              {paragraph}
            </p>
          ))}
        </div>

        {/* Expandable extra paragraphs */}
        {extraParagraphs.length > 0 && (
          <div
            className={`transition-all duration-300 overflow-hidden ${
              isExpanded ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
            }`}
          >
            <div className="space-y-3 mt-3">
              {extraParagraphs.map((paragraph, pIndex) => (
                <p key={pIndex} className="text-gray-600 leading-relaxed text-sm">
                  {paragraph}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Read more / less button — only shown if there are extra paragraphs */}
        {extraParagraphs.length > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-4 flex items-center text-blue-600 hover:text-blue-800 transition-colors duration-200 text-sm font-medium"
          >
            {isExpanded ? "Read less" : "Read more"}
            <ChevronUp
              className={`ml-1 h-4 w-4 transition-transform duration-200 ${
                isExpanded ? "" : "rotate-180"
              }`}
            />
          </button>
        )}
      </div>
    </div>
  );
};

export default NewsCard;
