import { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const API_BASE_URL = '/api'
const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981']

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [activeTab, setActiveTab] = useState('overview')
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [twitterPage, setTwitterPage] = useState(1)
  const [redditPage, setRedditPage] = useState(1)

  // Data states
  const [overviewData, setOverviewData] = useState(null)
  const [socialData, setSocialData] = useState(null)
  const [sentimentData, setSentimentData] = useState(null)
  const [redditData, setRedditData] = useState(null)
  const [redditSentimentData, setRedditSentimentData] = useState(null)
  const [citationsData, setCitationsData] = useState(null)
  const [newsData, setNewsData] = useState(null)

  const handleLogin = async (e) => {
    e.preventDefault()
    setAuthError('')

    try {
      const response = await fetch(`${API_BASE_URL}/auth`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      })

      const data = await response.json()

      if (data.success) {
        setToken(data.token)
        setIsAuthenticated(true)
        localStorage.setItem('auth_token', data.token)
      } else {
        setAuthError('Invalid password')
      }
    } catch (error) {
      setAuthError('Authentication failed')
    }
  }

  const fetchData = async (endpoint, setData) => {
    setLoading(true)
    try {
      const separator = endpoint.includes('?') ? '&' : '?'
      const response = await fetch(`${API_BASE_URL}${endpoint}${separator}t=${Date.now()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (!response.ok) {
        // Handle unauthorized access by returning to login
        if (response.status === 401) {
          setAuthError('Session expired or unauthorized. Please login.')
          setIsAuthenticated(false)
          setToken('')
          localStorage.removeItem('auth_token')
        } else {
          console.error(`API ${endpoint} returned status ${response.status}`)
        }
        setLoading(false)
        return
      }

      const data = await response.json()
      setData(data)
    } catch (error) {
      console.error(`Error fetching ${endpoint}:`, error)
    }
    setLoading(false)
  }

  useEffect(() => {
    const savedToken = localStorage.getItem('auth_token')
    if (savedToken) {
      setToken(savedToken)
      setIsAuthenticated(true)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated && token) {
      if (activeTab === 'overview') fetchData('/overview', setOverviewData)
      if (activeTab === 'twitter') {
        fetchData('/social?historic=1', setSocialData)
        fetchData('/sentiment?platform=Twitter', setSentimentData)
        setTwitterPage(1)
      }
      if (activeTab === 'reddit') {
        fetchData('/social?historic=1', setRedditData)
        fetchData('/sentiment?platform=Reddit', setRedditSentimentData)
        setRedditPage(1)
      }
      if (activeTab === 'citations') fetchData('/citations', setCitationsData)
      if (activeTab === 'news') fetchData('/news', setNewsData)
    }
  }, [activeTab, isAuthenticated, token])

  // If twitter data has no recent mentions, try fetching historical mentions
  useEffect(() => {
    if (isAuthenticated && token && activeTab === 'twitter' && socialData) {
      const recent = (socialData && socialData.recent_mentions) ? socialData.recent_mentions : []
      if (Array.isArray(recent) && recent.length === 0) {
        // fetch historic mentions and overwrite socialData if found
        (async () => {
          try {
            const resp = await fetch(`${API_BASE_URL}/social?historic=1&t=${Date.now()}`, { headers: { 'Authorization': `Bearer ${token}` } })
            if (!resp.ok) return
            const historic = await resp.json()
            if (historic && Array.isArray(historic.recent_mentions) && historic.recent_mentions.length > 0) {
              setSocialData(historic)
            }
          } catch (e) {
            console.error('Historic social fetch error', e)
          }
        })()
      }
    }
  }, [socialData, activeTab, isAuthenticated, token])

  // If reddit data has no recent mentions, try fetching historical mentions
  useEffect(() => {
    if (isAuthenticated && token && activeTab === 'reddit' && redditData) {
      const recent = (redditData && redditData.recent_mentions) ? redditData.recent_mentions : []
      if (Array.isArray(recent) && recent.length === 0) {
        // fetch historic mentions and overwrite redditData if found
        (async () => {
          try {
            const resp = await fetch(`${API_BASE_URL}/social?historic=1&t=${Date.now()}`, { headers: { 'Authorization': `Bearer ${token}` } })
            if (!resp.ok) return
            const historic = await resp.json()
            if (historic && Array.isArray(historic.recent_mentions) && historic.recent_mentions.length > 0) {
              setRedditData(historic)
            }
          } catch (e) {
            console.error('Historic reddit fetch error', e)
          }
        })()
      }
    }
  }, [redditData, activeTab, isAuthenticated, token])

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-xl w-96">
          <h1 className="text-3xl font-bold text-gray-800 mb-6 text-center">
            Ummatics Impact Monitor
          </h1>
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block text-gray-700 text-sm font-semibold mb-2">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter dashboard password"
                required
              />
            </div>
            {authError && (
              <div className="mb-4 text-red-500 text-sm">{authError}</div>
            )}
            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition"
            >
              Login
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">
              Ummatics Impact Monitor
            </h1>
            <button
              onClick={() => {
                setIsAuthenticated(false)
                setToken('')
                localStorage.removeItem('auth_token')
              }}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {['overview', 'twitter', 'reddit', 'citations', 'news'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm capitalize`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          </div>
        )}

        {!loading && activeTab === 'overview' && overviewData && (
          <OverviewTab data={overviewData} />
        )}
        {!loading && activeTab === 'twitter' && socialData && (
          <TwitterTab data={socialData} sentimentData={sentimentData} page={twitterPage} setPage={setTwitterPage} />
        )}
        {!loading && activeTab === 'reddit' && redditData && (
          <RedditTab data={redditData} sentimentData={redditSentimentData} page={redditPage} setPage={setRedditPage} />
        )}
        {!loading && activeTab === 'citations' && citationsData && (
          <CitationsTab data={citationsData} />
        )}
        {!loading && activeTab === 'news' && newsData && (
          <NewsTab data={newsData} />
        )}
      </main>
    </div>
  )
}

// Overview Tab Component
function OverviewTab({ data }) {
  // Be defensive against incomplete API responses
  const current_week = (data && data.current_week) ? data.current_week : {
    news_mentions: 0,
    social_mentions: 0,
    citations: 0
  }

  const weekly_trends = (data && data.weekly_trends) ? data.weekly_trends : []
  const recent_mentions = (data && data.recent_mentions) ? data.recent_mentions : []
  const platform_breakdown = (data && data.platform_breakdown) ? data.platform_breakdown : []
  const sentiment_summary = (data && data.sentiment_summary) ? data.sentiment_summary : []
  const top_subreddits = (data && data.top_subreddits) ? data.top_subreddits : []
  const trending_keywords = (data && data.trending_keywords) ? data.trending_keywords : []

  return (
    <div className="space-y-6">
      {/* Current Week Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="News Mentions"
          value={current_week.news_mentions}
          color="blue"
        />
        <MetricCard
          title="Social Mentions"
          value={current_week.social_mentions}
          color="purple"
        />
        <MetricCard
          title="Citations"
          value={current_week.citations}
          color="green"
        />
      </div>

      {/* Platform Breakdown and Sentiment Summary Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Breakdown Pie Chart */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Platform Breakdown (This Week)</h2>
          {platform_breakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={platform_breakdown}
                  dataKey="mention_count"
                  nameKey="platform"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ platform, mention_count }) => `${platform}: ${mention_count}`}
                >
                  {platform_breakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-8">No platform data for this week</p>
          )}
        </div>

        {/* Sentiment Summary */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Sentiment Summary (This Week)</h2>
          {sentiment_summary.length > 0 ? (
            <div className="space-y-4">
              {sentiment_summary.map((item, idx) => (
                <div key={idx} className="border-b pb-3 last:border-b-0">
                  <div className="font-medium text-gray-900 mb-2">{item.platform}</div>
                  <div className="flex gap-4 text-sm">
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-green-600">Positive</span>
                        <span className="font-semibold">{Math.round(item.positive_pct)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-green-500 h-2 rounded-full" style={{ width: `${item.positive_pct}%` }}></div>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-4 text-sm mt-2">
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-600">Neutral</span>
                        <span className="font-semibold">{Math.round(item.neutral_pct)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-gray-400 h-2 rounded-full" style={{ width: `${item.neutral_pct}%` }}></div>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-4 text-sm mt-2">
                    <div className="flex-1">
                      <div className="flex justify-between mb-1">
                        <span className="text-red-600">Negative</span>
                        <span className="font-semibold">{Math.round(item.negative_pct)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-red-500 h-2 rounded-full" style={{ width: `${item.negative_pct}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No sentiment data for this week</p>
          )}
        </div>
      </div>

      {/* Recent Mentions and Trending Keywords Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Mentions */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Recent Mentions</h2>
          {recent_mentions.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {recent_mentions.map((mention, idx) => (
                <div key={idx} className="border-b pb-3 last:border-b-0">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-sm text-blue-600">{mention.platform}</span>
                    <span className="text-xs text-gray-500">
                      {new Date(mention.date).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 mb-1">
                    {mention.text && mention.text.length > 150 
                      ? mention.text.substring(0, 150) + '...' 
                      : mention.text}
                  </p>
                  <div className="flex justify-between items-center text-xs text-gray-500">
                    <span>@{mention.author}</span>
                    {mention.engagement_score && (
                      <span className="text-purple-600">Engagement: {mention.engagement_score}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No recent mentions</p>
          )}
        </div>

        {/* Trending Keywords */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Trending Keywords (This Week)</h2>
          {trending_keywords.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {trending_keywords.map((keyword, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                >
                  {keyword.word}
                  <span className="ml-2 text-xs text-blue-600">({keyword.frequency})</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No trending keywords</p>
          )}
        </div>
      </div>

      {/* Top Subreddits */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Recently Discovered Subreddits</h2>
        {top_subreddits.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {top_subreddits.map((subreddit, idx) => (
              <div key={idx} className="border rounded-lg p-3 hover:bg-gray-50">
                <div className="font-medium text-blue-600">r/{subreddit.subreddit_name}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {new Date(subreddit.discovered_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">No subreddits discovered yet</p>
        )}
      </div>

      {/* Weekly Trends Chart with Logarithmic Scale */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">12-Week Trends (Logarithmic Scale)</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={weekly_trends.sort((a, b) => new Date(a.week_start_date) - new Date(b.week_start_date))}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="week_start_date"
              tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis scale="log" domain={['auto', 'auto']} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="total_news_mentions" stroke="#3b82f6" name="News" />
            <Line type="monotone" dataKey="total_social_mentions" stroke="#8b5cf6" name="Social" />
            <Line type="monotone" dataKey="total_citations" stroke="#10b981" name="Citations" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Twitter Tab Component
function TwitterTab({ data, sentimentData, page, setPage }) {
  const { platform_metrics, recent_mentions } = data

  // Filter for Twitter only
  const twitterMetrics = platform_metrics.filter(m => m.platform === 'Twitter')
  const twitterMentions = recent_mentions.filter(m => m.platform === 'Twitter')

  // Filter to Oct 2025+ and use daily data (no monthly aggregation)
  const dailyMetrics = twitterMetrics
    .map(metricRaw => ({
      ...metricRaw,
      _date: metricRaw.date || metricRaw.week_start_date || metricRaw.week_start
    }))
    .filter(metric => new Date(metric._date) >= new Date('2025-10-01'))
    .map(metric => ({
      date: metric._date,
      follower_count: metric.follower_count,
      mentions_count: metric.mentions_count || 0,
      engagement_rate: metric.engagement_rate || 0
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date))

  // Group metrics by platform and get latest follower count.
  const platformData = { Twitter: dailyMetrics }
  const latestFollowers = {}

  twitterMetrics.forEach(metricRaw => {
    const metric = { ...metricRaw, _date: metricRaw.date || metricRaw.week_start_date || metricRaw.week_start }
    
    // Track latest follower count (most recent date)
    const existing = latestFollowers[metric.platform]
    if (!existing || new Date(metric._date) > new Date(existing._date)) {
      latestFollowers[metric.platform] = {
        count: metric.follower_count,
        _date: metric._date,
        created_at: metric.created_at || metric.posted_at || metric._date
      }
    }
  })

  // Merge sentiment info into recent_mentions when available
  let enhancedRecent = recent_mentions || []
  let sentimentSeriesFromMentions = null
  if (sentimentData) {
    // If sentimentData has per-mention list, index by post_url
    const categorized = Array.isArray(sentimentData.categorized_mentions) ? sentimentData.categorized_mentions : (Array.isArray(sentimentData) ? sentimentData : null)
    const byUrl = {}
    if (categorized) {
      categorized.forEach(m => {
        if (m.post_url) byUrl[m.post_url] = m
      })

      // compute daily aggregates from categorized mentions if daily_metrics not present
      const dailyMap = {}
      categorized.forEach(m => {
        const date = m.posted_at ? (new Date(m.posted_at)).toISOString().slice(0,10) : null
        const score = m.sentiment_score !== undefined && m.sentiment_score !== null ? parseFloat(m.sentiment_score) : null
        if (!date || score === null || isNaN(score)) return
        if (!dailyMap[date]) dailyMap[date] = { sum: 0, count: 0 }
        dailyMap[date].sum += score
        dailyMap[date].count += 1
      })
      const series = Object.entries(dailyMap).map(([date, v]) => ({ date, average_sentiment_score: v.sum / v.count }))
      sentimentSeriesFromMentions = series.sort((a,b) => new Date(a.date) - new Date(b.date))
    }

    // Merge into recent mentions by post_url
    enhancedRecent = (twitterMentions || []).map(m => {
      if (m.post_url && byUrl[m.post_url]) {
        return { ...m, sentiment: byUrl[m.post_url].sentiment, sentiment_score: byUrl[m.post_url].sentiment_score }
      }
      return m
    })
  }

  return (
    <div className="space-y-6">
      {/* Follower Count Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Object.entries(latestFollowers).map(([platform, data]) => (
          <div key={platform} className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{platform} Followers</h3>
            <p className="text-4xl font-bold text-blue-600">{data.count.toLocaleString()}</p>
            <p className="text-sm text-gray-500 mt-2">
              Updated {new Date(data.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} at {new Date(data.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
        ))}
      </div>

      {/* Sentiment Trend (monthly averages for full history) */}
      {sentimentData && (() => {
        // Determine which key contains an array of daily metrics (be defensive about the shape)
        let raw = []
        if (Array.isArray(sentimentData)) raw = sentimentData
        else if (Array.isArray(sentimentData.sentiment_metrics)) raw = sentimentData.sentiment_metrics
        else if (Array.isArray(sentimentData.daily_metrics)) raw = sentimentData.daily_metrics
        else if (Array.isArray(sentimentData.metrics)) raw = sentimentData.metrics

        // Filter for Twitter platform only
        if (Array.isArray(raw) && raw.length > 0) {
          raw = raw.filter(item => item.platform === 'Twitter')
        }

        // If we don't have daily metrics but we computed a series from categorized mentions, use that
        if ((!Array.isArray(raw) || raw.length === 0) && Array.isArray(sentimentSeriesFromMentions) && sentimentSeriesFromMentions.length) {
          raw = sentimentSeriesFromMentions.map(x => ({ date: x.date, average_sentiment_score: x.average_sentiment_score }))
        }

        if (!Array.isArray(raw) || raw.length === 0) return null

        const sentimentSeries = raw.map(item => ({
          _date: item.date || item.week_start_date || item._date,
          avg_sentiment: (item.average_sentiment_score ?? item.avg_score ?? item.avg_sentiment ?? item.average_score)
        })).filter(s => s._date && (s.avg_sentiment !== undefined && s.avg_sentiment !== null) && s.avg_sentiment !== 0).slice()

        if (!sentimentSeries.length) return null

        // Filter to Oct 2025+ and use daily data (no monthly aggregation)
        const dailySentimentData = sentimentSeries
          .filter(item => new Date(item._date) >= new Date('2025-10-01'))
          .map(item => ({
            date: item._date,
            avg_sentiment: item.avg_sentiment
          }))
          .sort((a, b) => new Date(a.date) - new Date(b.date))

        return (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Average Sentiment (Daily - Oct 2025 onwards)</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={dailySentimentData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="avg_sentiment" stroke="#ef4444" name="Avg Sentiment" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )
      })()}

      {/* Platform Metrics */}
      {Object.entries(platformData).map(([platform, metrics]) => (
        <div key={platform} className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">{platform} Metrics (Daily - Oct 2025 onwards)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" domain={[0, 'auto']} />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="follower_count" stroke="#3b82f6" name="Followers" strokeWidth={2} connectNulls={false} />
              <Line yAxisId="right" type="monotone" dataKey="mentions_count" stroke="#10b981" name="Mentions" strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="engagement_rate" stroke="#f59e0b" name="Engagement Rate (%)" strokeWidth={2} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* All Mentions with Pagination */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">All Twitter Mentions ({enhancedRecent.length} total, {Math.ceil(enhancedRecent.length / 20)} pages)</h2>
          <button
            onClick={() => {
              const csv = [
                ['Platform', 'Author', 'Content', 'Posted At', 'Likes', 'Retweets', 'Replies', 'Sentiment', 'Score', 'URL'].join(','),
                ...enhancedRecent.map(m => [
                  m.platform || '',
                  m.author || '',
                  `"${(m.content || '').replace(/"/g, '""')}"`,
                  m.posted_at || '',
                  m.likes || 0,
                  m.retweets || 0,
                  m.replies || 0,
                  m.sentiment || '',
                  m.sentiment_score || '',
                  m.post_url || ''
                ].join(','))
              ].join('\n')
              const blob = new Blob([csv], { type: 'text/csv' })
              const url = window.URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `twitter-mentions-${new Date().toISOString().split('T')[0]}.csv`
              document.body.appendChild(a)
              a.click()
              document.body.removeChild(a)
              window.URL.revokeObjectURL(url)
            }}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
          >
            📥 Download CSV
          </button>
        </div>
        <div className="space-y-4">
          {enhancedRecent.slice((page - 1) * 20, page * 20).map((mention, idx) => {
            const rawScore = mention.sentiment_score ?? mention.score ?? null
            const score = rawScore !== null && rawScore !== undefined ? parseFloat(rawScore) : null
            let sentimentLabel = mention.sentiment
            if (!sentimentLabel && typeof score === 'number' && !isNaN(score)) {
              if (score > 0.1) sentimentLabel = 'positive'
              else if (score < -0.1) sentimentLabel = 'negative'
              else sentimentLabel = 'neutral'
            }

            const badgeColor = sentimentLabel === 'positive' ? 'bg-green-100 text-green-700' : sentimentLabel === 'negative' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'

            return (
              <div key={idx} className="border-b pb-4 last:border-b-0">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-blue-600">{mention.platform}</span>
                      <span className="text-sm text-gray-500">@{mention.author}</span>
                      {sentimentLabel && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${badgeColor} ml-3`}>{sentimentLabel}</span>
                      )}
                    </div>
                    <p className="text-gray-700 mt-1">{mention.content}</p>
                    {mention.post_url && (
                      <a 
                        href={mention.post_url} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                      >
                        View post
                      </a>
                    )}
                    <div className="flex gap-4 mt-2 text-sm text-gray-500">
                      <span>{mention.likes} likes</span>
                      <span>{mention.retweets} retweets</span>
                      <span>{mention.replies} replies</span>
                      {typeof score === 'number' && (
                        <span>score: {score.toFixed(2)}</span>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">
                    {mention.posted_at ? new Date(mention.posted_at).toLocaleDateString() : (mention.created_at ? new Date(mention.created_at).toLocaleDateString() : '')}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
        {/* Pagination Controls */}
        {enhancedRecent.length > 20 && (
          <div className="flex flex-col gap-4 mt-6">
            <div className="flex justify-center items-center gap-4">
              <button
                onClick={() => setPage(1)}
                disabled={page === 1}
                className="px-3 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700 text-sm"
              >
                First
              </button>
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {page} of {Math.ceil(enhancedRecent.length / 20)}
              </span>
              <button
                onClick={() => setPage(Math.min(Math.ceil(enhancedRecent.length / 20), page + 1))}
                disabled={page >= Math.ceil(enhancedRecent.length / 20)}
                className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700"
              >
                Next
              </button>
              <button
                onClick={() => setPage(Math.ceil(enhancedRecent.length / 20))}
                disabled={page >= Math.ceil(enhancedRecent.length / 20)}
                className="px-3 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700 text-sm"
              >
                Last
              </button>
            </div>
            <div className="flex justify-center items-center gap-2">
              <label htmlFor="pageJump" className="text-sm text-gray-600">Jump to page:</label>
              <input
                id="pageJump"
                type="number"
                min="1"
                max={Math.ceil(enhancedRecent.length / 20)}
                value={page}
                onChange={(e) => {
                  const val = parseInt(e.target.value)
                  if (val >= 1 && val <= Math.ceil(enhancedRecent.length / 20)) {
                    setPage(val)
                  }
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-center"
              />
              <span className="text-sm text-gray-500">of {Math.ceil(enhancedRecent.length / 20)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Reddit Tab Component
function RedditTab({ data, sentimentData, page, setPage }) {
  const { platform_metrics, recent_mentions } = data

  // Filter for Reddit only
  const redditMetrics = platform_metrics.filter(m => m.platform === 'Reddit')
  const redditMentions = recent_mentions.filter(m => m.platform === 'Reddit')

  // Group metrics by platform and get latest follower count.
  // Normalize date fields (daily data may use `date` instead of `week_start_date`).
  const platformData = {}
  const latestFollowers = {}

  redditMetrics.forEach(metricRaw => {
    const metric = { ...metricRaw, _date: metricRaw.date || metricRaw.week_start_date || metricRaw.week_start }

    if (!platformData[metric.platform]) {
      platformData[metric.platform] = []
    }
    platformData[metric.platform].push(metric)

    // Track latest follower count (most recent date)
    const existing = latestFollowers[metric.platform]
    if (!existing || new Date(metric._date) > new Date(existing._date)) {
      latestFollowers[metric.platform] = {
        count: metric.follower_count,
        _date: metric._date,
        created_at: metric.created_at || metric.posted_at || metric._date
      }
    }
  })

  // Merge sentiment info into recent_mentions when available
  let enhancedRecent = redditMentions || []
  let sentimentSeriesFromMentions = null
  if (sentimentData) {
    // If sentimentData has per-mention list, index by post_url
    const categorized = Array.isArray(sentimentData.categorized_mentions) ? sentimentData.categorized_mentions : (Array.isArray(sentimentData) ? sentimentData : null)
    const byUrl = {}
    if (categorized) {
      categorized.forEach(m => {
        if (m.post_url) byUrl[m.post_url] = m
      })

      // compute daily aggregates from categorized mentions if daily_metrics not present
      const dailyMap = {}
      categorized.forEach(m => {
        const date = m.posted_at ? (new Date(m.posted_at)).toISOString().slice(0,10) : null
        const score = m.sentiment_score !== undefined && m.sentiment_score !== null ? parseFloat(m.sentiment_score) : null
        if (!date || score === null || isNaN(score)) return
        if (!dailyMap[date]) dailyMap[date] = { sum: 0, count: 0 }
        dailyMap[date].sum += score
        dailyMap[date].count += 1
      })
      const series = Object.entries(dailyMap).map(([date, v]) => ({ date, average_sentiment_score: v.sum / v.count }))
      sentimentSeriesFromMentions = series.sort((a,b) => new Date(a.date) - new Date(b.date))
    }

    // Merge into recent mentions by post_url
    enhancedRecent = (redditMentions || []).map(m => {
      if (m.post_url && byUrl[m.post_url]) {
        return { ...m, sentiment: byUrl[m.post_url].sentiment, sentiment_score: byUrl[m.post_url].sentiment_score }
      }
      return m
    })
  }

  return (
    <div className="space-y-6">
      {/* Reddit doesn't have follower counts - removed this section */}

      {/* Sentiment Trend (daily averages) */}
      {sentimentData && (() => {
        // Determine which key contains an array of daily metrics (be defensive about the shape)
        let raw = []
        if (Array.isArray(sentimentData)) raw = sentimentData
        else if (Array.isArray(sentimentData.sentiment_metrics)) raw = sentimentData.sentiment_metrics
        else if (Array.isArray(sentimentData.daily_metrics)) raw = sentimentData.daily_metrics
        else if (Array.isArray(sentimentData.metrics)) raw = sentimentData.metrics

        // If we don't have daily metrics but we computed a series from categorized mentions, use that
        if ((!Array.isArray(raw) || raw.length === 0) && Array.isArray(sentimentSeriesFromMentions) && sentimentSeriesFromMentions.length) {
          raw = sentimentSeriesFromMentions.map(x => ({ date: x.date, average_sentiment_score: x.average_sentiment_score }))
        }

        if (!Array.isArray(raw) || raw.length === 0) return null

        const sentimentSeries = raw.map(item => ({
          _date: item.date || item.week_start_date || item._date,
          avg_sentiment: (item.average_sentiment_score ?? item.avg_score ?? item.avg_sentiment ?? item.average_score)
        })).filter(s => s._date && (s.avg_sentiment !== undefined && s.avg_sentiment !== null) && s.avg_sentiment !== 0).slice()

        if (!sentimentSeries.length) return null

        return (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Average Sentiment (Daily)</h2>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={sentimentSeries.sort((a, b) => new Date(a._date) - new Date(b._date))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="_date"
                  tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="avg_sentiment" stroke="#ef4444" name="Avg Sentiment" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )
      })()}

      {/* Platform Metrics */}
      {Object.entries(platformData).map(([platform, metrics]) => (
        <div key={platform} className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">{platform} Metrics</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics.sort((a, b) => new Date(a._date) - new Date(b._date))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="_date"
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis domain={[0, 'auto']} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="mentions_count" stroke="#10b981" name="Mentions" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* All Reddit Mentions with Pagination */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">All Reddit Mentions ({enhancedRecent.length} total, {Math.ceil(enhancedRecent.length / 20)} pages)</h2>
          {enhancedRecent.length > 0 && (
            <button
              onClick={() => {
                const csv = [
                  ['Platform', 'Author', 'Content', 'Posted At', 'Likes', 'Replies', 'Sentiment', 'Score', 'URL'].join(','),
                  ...enhancedRecent.map(m => [
                    m.platform || '',
                    m.author || '',
                    `"${(m.content || '').replace(/"/g, '""')}"`,
                    m.posted_at || '',
                    m.likes || 0,
                    m.replies || 0,
                    m.sentiment || '',
                    m.sentiment_score || '',
                    m.post_url || ''
                  ].join(','))
                ].join('\n')
                const blob = new Blob([csv], { type: 'text/csv' })
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `reddit-mentions-${new Date().toISOString().split('T')[0]}.csv`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
                window.URL.revokeObjectURL(url)
              }}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
            >
              📥 Download CSV
            </button>
          )}
        </div>
        {enhancedRecent.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No Reddit mentions found in database</p>
        ) : (
          <>
            <div className="space-y-4">
              {enhancedRecent.slice((page - 1) * 20, page * 20).map((mention, idx) => {
                const rawScore = mention.sentiment_score ?? mention.score ?? null
                const score = rawScore !== null && rawScore !== undefined ? parseFloat(rawScore) : null
                let sentimentLabel = mention.sentiment
                if (!sentimentLabel && typeof score === 'number' && !isNaN(score)) {
                  if (score > 0.1) sentimentLabel = 'positive'
                  else if (score < -0.1) sentimentLabel = 'negative'
                  else sentimentLabel = 'neutral'
                }

                const badgeColor = sentimentLabel === 'positive' ? 'bg-green-100 text-green-700' : sentimentLabel === 'negative' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'

                return (
                  <div key={idx} className="border-b pb-4 last:border-b-0">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-blue-600">{mention.platform}</span>
                          <span className="text-sm text-gray-500">u/{mention.author}</span>
                          {sentimentLabel && (
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${badgeColor} ml-3`}>{sentimentLabel}</span>
                          )}
                        </div>
                        <p className="text-gray-700 mt-1" dangerouslySetInnerHTML={{ __html: mention.content.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/<[^>]+>/g, '') }}></p>
                        {mention.post_url && (
                          <a
                            href={mention.post_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                          >
                            View post
                          </a>
                        )}
                        <div className="flex gap-4 mt-2 text-sm text-gray-500">
                          <span>{mention.likes} upvotes</span>
                          <span>{mention.replies} comments</span>
                          {typeof score === 'number' && (
                            <span>score: {score.toFixed(2)}</span>
                          )}
                        </div>
                      </div>
                      <span className="text-xs text-gray-400">
                        {mention.posted_at ? new Date(mention.posted_at).toLocaleDateString() : (mention.created_at ? new Date(mention.created_at).toLocaleDateString() : '')}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
            {/* Pagination Controls */}
            {enhancedRecent.length > 20 && (
              <div className="flex flex-col gap-4 mt-6">
                <div className="flex justify-center items-center gap-4">
                  <button
                    onClick={() => setPage(1)}
                    disabled={page === 1}
                    className="px-3 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700 text-sm"
                  >
                    First
                  </button>
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-600">
                    Page {page} of {Math.ceil(enhancedRecent.length / 20)}
                  </span>
                  <button
                    onClick={() => setPage(Math.min(Math.ceil(enhancedRecent.length / 20), page + 1))}
                    disabled={page >= Math.ceil(enhancedRecent.length / 20)}
                    className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700"
                  >
                    Next
                  </button>
                  <button
                    onClick={() => setPage(Math.ceil(enhancedRecent.length / 20))}
                    disabled={page >= Math.ceil(enhancedRecent.length / 20)}
                    className="px-3 py-2 bg-blue-600 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-blue-700 text-sm"
                  >
                    Last
                  </button>
                </div>
                <div className="flex justify-center items-center gap-2">
                  <label htmlFor="redditPageJump" className="text-sm text-gray-600">Jump to page:</label>
                  <input
                    id="redditPageJump"
                    type="number"
                    min="1"
                    max={Math.ceil(enhancedRecent.length / 20)}
                    value={page}
                    onChange={(e) => {
                      const val = parseInt(e.target.value)
                      if (val >= 1 && val <= Math.ceil(enhancedRecent.length / 20)) {
                        setPage(val)
                      }
                    }}
                    className="w-20 px-2 py-1 border border-gray-300 rounded text-center"
                  />
                  <span className="text-sm text-gray-500">of {Math.ceil(enhancedRecent.length / 20)}</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// Citations Tab Component
function CitationsTab({ data }) {
  const { weekly_metrics, top_works, recent_citations } = data

  // Icon components for citation types
  const OrganizationIcon = () => (
    <svg className="inline w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Organization/Institution Citation">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
    </svg>
  )

  const WordIcon = () => (
    <svg className="inline w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Word/Concept Usage">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )

  const getCitationIcon = (citationType) => {
    if (citationType === 'organization') return <OrganizationIcon />
    if (citationType === 'word') return <WordIcon />
    return null
  }

  return (
    <div className="space-y-6">
      {/* Citation Type Legend */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-blue-900 mb-2">Citation Types:</h3>
        <div className="flex gap-6 text-sm text-blue-800">
          <div className="flex items-center">
            <OrganizationIcon />
            <span>Organization/Institution (ummatics.org)</span>
          </div>
          <div className="flex items-center">
            <WordIcon />
            <span>Word/Concept Usage (ummatic)</span>
          </div>
        </div>
      </div>

      {/* Citation Trends */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Citation Growth</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={weekly_metrics.sort((a, b) => new Date(a.week_start_date) - new Date(b.week_start_date))}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="week_start_date"
              tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="total_citations" stroke="#3b82f6" name="Total Citations" />
            <Line type="monotone" dataKey="new_citations_this_week" stroke="#10b981" name="New This Week" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Top Cited Works */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Recently Mentioned Works</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Authors</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Year</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Citations</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Most Recent Mention</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {top_works.slice(0, 10).map((work, idx) => (
                <tr key={idx}>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <div className="flex items-start">
                      {getCitationIcon(work.citation_type)}
                      <div className="flex-1">
                        {work.doi ? (
                          <a href={`https://doi.org/${work.doi}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                            {work.title}
                          </a>
                        ) : work.title}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{work.authors?.slice(0, 50)}...</td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {work.publication_date ? new Date(work.publication_date).getFullYear() : 'N/A'}
                  </td>
                  <td className="px-6 py-4 text-sm font-semibold text-gray-900">{work.cited_by_count}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {work.publication_date ? new Date(work.publication_date).toLocaleDateString('en-US', { 
                      year: 'numeric', 
                      month: 'short', 
                      day: 'numeric' 
                    }) : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// News Tab Component
function NewsTab({ data }) {
  const { news_mentions, weekly_counts } = data

  return (
    <div className="space-y-6">
      {/* Weekly News Mentions Chart */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4\">News Mentions by Week</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={weekly_counts.sort((a, b) => new Date(a.week_start_date) - new Date(b.week_start_date))}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="week_start_date"
              tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis />
            <Tooltip />
            <Bar dataKey="mention_count" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent News Mentions */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Recent News Mentions</h2>
        <div className="space-y-4">
          {news_mentions.sort((a, b) => new Date(b.published_at) - new Date(a.published_at)).map((mention, idx) => (
            <div key={idx} className="border-b pb-4 last:border-b-0">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900 mb-1">
                    <a href={mention.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600">
                      {mention.title}
                    </a>
                  </h3>
                  <p className="text-sm text-gray-600 mb-2">{mention.snippet}</p>
                  <div className="flex gap-4 text-xs text-gray-500">
                    <span>Source: {mention.source}</span>
                    <span>
                      {mention.published_at && new Date(mention.published_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Metric Card Component
function MetricCard({ title, value, color }) {
  const colorClasses = {
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
    green: 'bg-green-500',
    orange: 'bg-orange-500'
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className={`inline-block p-3 rounded-lg ${colorClasses[color]} bg-opacity-10 mb-4`}>
        <div className={`w-6 h-6 ${colorClasses[color]} rounded`}></div>
      </div>
      <h3 className="text-sm font-medium text-gray-600 mb-1">{title}</h3>
      <p className="text-3xl font-bold text-gray-900">{value.toLocaleString()}</p>
    </div>
  )
}

export default App
