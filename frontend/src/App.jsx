import React, { useState, useEffect, useCallback, useRef } from "react";
import Navbar from "./components/Navbar";
import NewsList from "./components/NewsList";
import Footer from "./components/Footer";

const API_BASE = "/api";

// ── Pipeline progress stages → user-friendly labels ──────────────────────────
const STAGE_LABELS = {
  idle:       "Waiting to start...",
  Starting:   "Initialising pipeline...",
  "Fetching RSS feeds":   "Fetching news from 30+ sources...",
  "Fetching NewsAPI":     "Fetching additional sources...",
  Deduplicating:          "Removing duplicate stories...",
  "Scraping articles":    "Reading full articles...",
  Complete:   "Done!",
  Error:      "Pipeline error",
};

const label = (stage = "") =>
  Object.entries(STAGE_LABELS).find(([k]) => stage.startsWith(k))?.[1] ?? stage;

// ── App ───────────────────────────────────────────────────────────────────────
const App = () => {
  const [news, setNews]                   = useState([]);
  const [categories, setCategories]       = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [searchQuery, setSearchQuery]     = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage]                   = useState(1);
  const [hasMore, setHasMore]             = useState(true);
  const [error, setError]                 = useState(null);
  const [loading, setLoading]             = useState(true);
  const [loadingMore, setLoadingMore]     = useState(false);
  const [pipeline, setPipeline]           = useState({ stage: "idle", percent: 0 });
  const [pipelineReady, setPipelineReady] = useState(false);
  const [backendDown, setBackendDown]     = useState(false);
  const LIMIT = 12;

  // ── Debounce search input (400ms) ──────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 400);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // Reset to page 1 when category or search changes
  useEffect(() => {
    setPage(1);
    setNews([]);
  }, [selectedCategory, debouncedSearch]);

  // ── Fetch categories once ──────────────────────────────────────────────────
  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/categories`);
      if (!res.ok) return;
      const data = await res.json();
      setCategories(data.categories || []);
    } catch (_) {}
  }, []);

  // ── Poll pipeline progress ─────────────────────────────────────────────────
  const pollProgress = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/progress`);
      if (!res.ok) return;
      const data = await res.json();
      setPipeline(data);
      if (data.stage === "Complete" || data.articles_saved > 0) {
        setPipelineReady(true);
      }
    } catch (_) {
      setBackendDown(true);
    }
  }, []);

  // ── Fetch news articles ────────────────────────────────────────────────────
  const fetchNews = useCallback(async (pageNum = 1, append = false) => {
    try {
      if (pageNum === 1) setLoading(true);
      else setLoadingMore(true);
      setError(null);
      setBackendDown(false);

      const params = new URLSearchParams({
        page:  pageNum,
        limit: LIMIT,
        ...(selectedCategory !== "All" && { category: selectedCategory }),
        ...(debouncedSearch && { search: debouncedSearch }),
      });

      const res = await fetch(`${API_BASE}/news?${params}`);

      if (!res.ok) {
        if (res.status === 503 || res.status === 404) {
          setError("pipeline_running");
          return;
        }
        throw new Error(`Server error ${res.status}`);
      }

      const data = await res.json();
      const articles = data.news || [];

      if (append) {
        setNews(prev => [...prev, ...articles]);
      } else {
        setNews(articles);
      }

      setHasMore(articles.length === LIMIT);
    } catch (err) {
      if (err.name === "TypeError") {
        setBackendDown(true);
        setError("backend_down");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [selectedCategory, debouncedSearch]);

  // ── Load more (pagination) ─────────────────────────────────────────────────
  const loadMore = () => {
    const next = page + 1;
    setPage(next);
    fetchNews(next, true);
  };

  // ── Initial setup & polling ────────────────────────────────────────────────
  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    fetchNews(1, false);
  }, [fetchNews]);

  // Poll progress every 4s while pipeline is running, stop when done
  useEffect(() => {
    pollProgress();
    if (pipelineReady) return;
    const interval = setInterval(pollProgress, 4000);
    return () => clearInterval(interval);
  }, [pollProgress, pipelineReady]);

  // Auto-refresh news every 6 hours
  useEffect(() => {
    const interval = setInterval(() => fetchNews(1, false), 6 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchNews]);

  // ── Render ─────────────────────────────────────────────────────────────────
  const isPipelineRunning = !pipelineReady && pipeline.stage !== "idle";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar
        categories={categories}
        selectedCategory={selectedCategory}
        onCategoryChange={(cat) => { setSelectedCategory(cat); }}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      <main className="container mx-auto px-4 py-8 flex-1">

        {/* ── Backend down banner ─────────────────────────────────────────── */}
        {backendDown && (
          <div className="bg-red-50 border border-red-300 text-red-800 px-4 py-4 rounded-lg mb-6 flex items-start gap-3">
            <span className="text-xl">🔴</span>
            <div>
              <p className="font-semibold">Backend server is not running</p>
              <code className="text-xs bg-red-100 px-2 py-1 rounded mt-1 inline-block">
                cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python3 server.py
              </code>
            </div>
          </div>
        )}

        {/* ── Pipeline progress bar ───────────────────────────────────────── */}
        {isPipelineRunning && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-4 mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-blue-800 font-medium text-sm">
                🤖 {label(pipeline.stage)}
              </span>
              <span className="text-blue-600 text-sm font-mono">
                {pipeline.percent}%
              </span>
            </div>
            <div className="w-full bg-blue-100 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-700 ease-out"
                style={{ width: `${pipeline.percent}%` }}
              />
            </div>
            {pipeline.articles_found > 0 && (
              <p className="text-blue-600 text-xs mt-2">
                {pipeline.articles_saved} / {pipeline.articles_found} articles processed
              </p>
            )}
          </div>
        )}

        {/* ── Page heading ────────────────────────────────────────────────── */}
        {!loading && (
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800">
              {debouncedSearch
                ? `Search: "${debouncedSearch}"`
                : selectedCategory === "All"
                  ? "Latest News"
                  : `${selectedCategory} News`}
            </h1>
            {news.length > 0 && (
              <span className="text-sm text-gray-400">{news.length} articles</span>
            )}
          </div>
        )}

        {/* ── Loading spinner ──────────────────────────────────────────────── */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
            <p className="text-gray-500 text-sm">
              {isPipelineRunning ? "Waiting for pipeline to finish..." : "Loading articles..."}
            </p>
          </div>
        )}

        {/* ── Empty state ──────────────────────────────────────────────────── */}
        {!loading && !backendDown && news.length === 0 && (
          <div className="text-center py-20 text-gray-400">
            {debouncedSearch ? (
              <>
                <p className="text-5xl mb-4">🔍</p>
                <p className="text-xl font-medium">No results for "{debouncedSearch}"</p>
                <p className="text-sm mt-2">Try a different keyword</p>
              </>
            ) : isPipelineRunning ? (
              <>
                <p className="text-5xl mb-4">⏳</p>
                <p className="text-xl font-medium">Pipeline is processing news...</p>
                <p className="text-sm mt-2">Articles will appear automatically — usually takes 2-3 minutes</p>
              </>
            ) : (
              <>
                <p className="text-5xl mb-4">📭</p>
                <p className="text-xl font-medium">No articles yet</p>
                <p className="text-sm mt-2">The pipeline hasn't run yet or no articles matched this category</p>
              </>
            )}
          </div>
        )}

        {/* ── News grid ────────────────────────────────────────────────────── */}
        {!loading && news.length > 0 && (
          <>
            <NewsList news={news} />

            {/* Load more */}
            {hasMore && (
              <div className="flex justify-center mt-8">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="px-8 py-3 bg-blue-600 text-white rounded-full font-medium
                             hover:bg-blue-700 active:scale-95 transition-all duration-200
                             disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loadingMore ? "Loading..." : "Load more"}
                </button>
              </div>
            )}
          </>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default App;
