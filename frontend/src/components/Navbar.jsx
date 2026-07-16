import React, { useState } from "react";
import { Newspaper, ChevronDown, Search, X } from "lucide-react";

const Navbar = ({
  categories = [],
  selectedCategory,
  onCategoryChange,
  searchQuery,
  onSearchChange,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Use categories from API; fall back to defaults if still loading
  const catList = categories.length > 0
    ? categories
    : ["All", "Technology", "Politics", "Business", "Sports", "Science", "Health", "Entertainment", "India"];

  return (
    <nav className="sticky top-0 bg-white shadow-md z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16 gap-4">

          {/* ── Logo ─────────────────────────────────────────────────────── */}
          <div className="flex items-center shrink-0">
            <Newspaper className="h-8 w-8 text-blue-600" />
            <span className="ml-2 text-xl font-bold text-gray-800 hidden sm:block">
              NewsPilot AI
            </span>
          </div>

          {/* ── Search bar ───────────────────────────────────────────────── */}
          <div className="flex-1 max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search news..."
              className="w-full pl-9 pr-8 py-2 text-sm border border-gray-200 rounded-full
                         focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent
                         transition-all duration-200 bg-gray-50"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* ── Category dropdown ─────────────────────────────────────────── */}
          <div className="relative shrink-0">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-1 px-4 py-2 rounded-full bg-blue-600 text-white
                         text-sm font-medium hover:bg-blue-700 active:scale-95
                         transition-all duration-200"
            >
              {selectedCategory === "All" ? "Categories" : selectedCategory}
              <ChevronDown
                className={`h-4 w-4 transition-transform duration-200 ${
                  isDropdownOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isDropdownOpen && (
              <>
                {/* Backdrop */}
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-52 bg-white rounded-xl shadow-xl
                                py-1 z-50 border border-gray-100 overflow-hidden">
                  {catList.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => {
                        onCategoryChange(cat);
                        setIsDropdownOpen(false);
                      }}
                      className={`block w-full text-left px-4 py-2.5 text-sm transition-colors duration-150 ${
                        selectedCategory === cat
                          ? "bg-blue-50 text-blue-700 font-semibold"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
