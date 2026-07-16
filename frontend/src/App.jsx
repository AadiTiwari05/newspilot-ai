import React, { useState, useEffect, useCallback } from "react";
import Navbar from "./components/Navbar";
import NewsList from "./components/NewsList";
import Footer from "./components/Footer";

// All API calls go through the Vite proxy at /api/*
// Vite forwards these to http://127.0.0.1:5000/* server-side — zero CORS issues.
const API_BASE = "/api";

const App = () => {
  const [news, setNews] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pipelineReady, setPipelineReady] = useState(false);
  const [backendDown, setBackendDown] = useState(false);

  // Robust content parser — handles multiple LLM output formats:
  // "Title: ...", "## ...", "# ...", "**Title**", plain first line
  const parseContent = (content) => {
    if (!content) return { title: "Untitled", paragraphs: [] };

    const lines = content.split("\n").filter((line) => line.trim());
    if (lines.length === 0) return { title: "Untitled", paragraphs: [] };

    let title = lines[0] || "Untitled";
    title = title
      .replace(/^#+\s*/, "")        // remove markdown heading hashes
      .replace(/^Title:\s*/i, "")   // remove "Title: " prefix
      .replace(/^\*+|\*+$/g, "")    // remove surrounding asterisks
      .trim();

    const paragraphs = lines.slice(1).reduce((acc, line) => {
      const trimmed = line.trim();
      // Skip section headers, markdown headings, separators, and empty lines
      if (
        !trimmed ||
        trimmed.endsWith(":") ||
        trimmed.startsWith("#") ||
        trimmed.startsWith("---") ||
        trimmed.startsWith("===") ||
        trimmed.startsWith("***")
      ) {
        return acc;
      }
      // Strip markdown bold/italic for clean display
      const clean = trimmed.replace(/\*\*/g, "").replace(/\*/g, "").trim();
      if (clean) acc.push(clean);
      return acc;
    }, []);

    return { title, paragraphs };
  };

  const fetchNews = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setBackendDown(false);

      // Check pipeline status first — uses proxy, no CORS
      let statusData = null;
      try {
        const statusRes = await fetch(`${API_BASE}/status`);
        if (statusRes.ok) {
          statusData = await statusRes.json();
        }
      } catch (statusErr) {
        // Backend is not running yet — show friendly message instead of crashing
        setBackendDown(true);
        setError("Backend server is not running. Please start it with: python3 server.py");
        setLoading(false);
        return;
      }

      if (statusData && !statusData.ready) {
        setError("⏳ AI pipeline is running — news will appear automatically once it finishes (5–15 min).");
        setLoading(false);
        return;
      }

      setPipelineReady(true);

      // Fetch news — uses proxy, no CORS
      const response = await fetch(`${API_BASE}/news`);
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (!data.news || !Array.isArray(data.news)) {
        throw new Error("Unexpected response format from /news endpoint");
      }

      const formattedNews = data.news.map((item) => {
        const { title, paragraphs } = parseContent(item.content);
        return {
          category: item.category || "General",
          title,
          paragraphs,
          image_urls: item.image_urls || null,
        };
      });

      const uniqueCategories = [
        "All",
        ...new Set(formattedNews.map((item) => item.category)),
      ];

      setNews(formattedNews);
      setCategories(uniqueCategories);
    } catch (err) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        setBackendDown(true);
        setError("Cannot connect to backend — make sure Python server is running on port 5000.");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNews();
    // Poll every 20s while pipeline is running, every 8 min once ready
    const interval = setInterval(fetchNews, pipelineReady ? 480000 : 20000);
    return () => clearInterval(interval);
  }, [fetchNews, pipelineReady]);

  const filteredNews =
    selectedCategory === "All"
      ? news
      : news.filter((item) => item.category === selectedCategory);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar
        categories={categories}
        selectedCategory={selectedCategory}
        onCategoryChange={setSelectedCategory}
      />

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div
            className={`border px-4 py-3 rounded mb-6 flex items-start gap-3 ${
              backendDown
                ? "bg-red-50 border-red-300 text-red-800"
                : "bg-yellow-50 border-yellow-300 text-yellow-800"
            }`}
          >
            <span className="text-lg mt-0.5">{backendDown ? "🔴" : "⏳"}</span>
            <div>
              <p className="font-medium">{error}</p>
              {backendDown && (
                <p className="text-sm mt-1 font-mono bg-red-100 px-2 py-1 rounded inline-block mt-2">
                  cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python3 server.py
                </p>
              )}
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col justify-center items-center py-20 gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="text-gray-500 text-sm">
              {pipelineReady ? "Loading news..." : "Waiting for pipeline..."}
            </p>
          </div>
        ) : (
          <>
            <h1 className="text-3xl font-bold text-gray-800 mb-8">
              {selectedCategory === "All" ? "Latest News" : `${selectedCategory} News`}
            </h1>

            {filteredNews.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <p className="text-xl">No articles available yet.</p>
                {!pipelineReady && (
                  <p className="text-sm mt-2">
                    The AI pipeline is still processing — page will refresh automatically.
                  </p>
                )}
              </div>
            ) : (
              <NewsList news={filteredNews} />
            )}
          </>
        )}
      </main>
      <Footer />
    </div>
  );
};

export default App;
