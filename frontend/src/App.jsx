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

  // Data states
  const [overviewData, setOverviewData] = useState(null)
  const [socialData, setSocialData] = useState(null)
  const [websiteData, setWebsiteData] = useState(null)
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
      const response = await fetch(`${API_BASE_URL}${endpoint}?t=${Date.now()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
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
      if (activeTab === 'social') fetchData('/social', setSocialData)
      if (activeTab === 'website') fetchData('/website', setWebsiteData)
      if (activeTab === 'citations') fetchData('/citations', setCitationsData)
      if (activeTab === 'news') fetchData('/news', setNewsData)
    }
  }, [activeTab, isAuthenticated, token])

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
            {['overview', 'social', 'website', 'citations', 'news'].map((tab) => (
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
        {!loading && activeTab === 'social' && socialData && (
          <SocialTab data={socialData} />
        )}
        {!loading && activeTab === 'website' && websiteData && (
          <WebsiteTab data={websiteData} />
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
  const { current_week, weekly_trends } = data

  return (
    <div className="space-y-6">
      {/* Current Week Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
        <MetricCard
          title="Website Sessions"
          value={current_week.website_sessions}
          color="orange"
        />
      </div>

      {/* Weekly Trends Chart with Logarithmic Scale */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">12-Week Trends (Logarithmic Scale)</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={weekly_trends.reverse()}>
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
            <Line type="monotone" dataKey="total_website_sessions" stroke="#f59e0b" name="Sessions" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Social Tab Component
function SocialTab({ data }) {
  const { platform_metrics, recent_mentions } = data

  // Group metrics by platform and get latest follower count
  const platformData = {}
  const latestFollowers = {}
  
  platform_metrics.forEach(metric => {
    if (!platformData[metric.platform]) {
      platformData[metric.platform] = []
    }
    platformData[metric.platform].push(metric)
    
    // Track latest follower count (most recent week)
    if (!latestFollowers[metric.platform] || new Date(metric.week_start_date) > new Date(latestFollowers[metric.platform].week_start_date)) {
      latestFollowers[metric.platform] = {
        count: metric.follower_count,
        week_start_date: metric.week_start_date,
        created_at: metric.created_at
      }
    }
  })

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

      {/* Platform Metrics */}
      {Object.entries(platformData).map(([platform, metrics]) => (
        <div key={platform} className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">{platform} Metrics</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics.reverse()}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="week_start_date"
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="follower_count" stroke="#3b82f6" name="Followers" />
              <Line yAxisId="right" type="monotone" dataKey="mentions_count" stroke="#10b981" name="Mentions" />
              <Line yAxisId="right" type="monotone" dataKey="engagement_rate" stroke="#f59e0b" name="Engagement Rate" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* Recent Mentions */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Recent Mentions</h2>
        <div className="space-y-4">
          {recent_mentions.slice(0, 20).map((mention, idx) => (
            <div key={idx} className="border-b pb-4 last:border-b-0">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <span className="text-sm font-medium text-blue-600">{mention.platform}</span>
                  <span className="text-sm text-gray-500 ml-2">@{mention.author}</span>
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
                  </div>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(mention.posted_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Website Tab Component
function WebsiteTab({ data }) {
  const { weekly_metrics, top_pages, geographic_data } = data

  return (
    <div className="space-y-6">
      {/* Weekly Traffic Chart */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Website Traffic Trends</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={weekly_metrics.reverse()}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="week_start_date"
              tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="total_sessions" stroke="#3b82f6" name="Sessions" />
            <Line type="monotone" dataKey="total_users" stroke="#10b981" name="Users" />
            <Line type="monotone" dataKey="total_pageviews" stroke="#f59e0b" name="Pageviews" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Top Pages */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Top Pages (Last Week)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={top_pages.slice(0, 10)} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="page_path" type="category" width={150} />
            <Tooltip />
            <Bar dataKey="pageviews" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Geographic Distribution */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Geographic Distribution</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={geographic_data.slice(0, 10)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="country" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="sessions" fill="#3b82f6" name="Sessions" />
            <Bar dataKey="users" fill="#10b981" name="Users" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Citations Tab Component
function CitationsTab({ data }) {
  const { weekly_metrics, top_works, recent_citations } = data

  return (
    <div className="space-y-6">
      {/* Citation Trends */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Citation Growth</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={weekly_metrics.reverse()}>
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
                    {work.doi ? (
                      <a href={`https://doi.org/${work.doi}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {work.title}
                      </a>
                    ) : work.title}
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
        <h2 className="text-xl font-semibold mb-4">News Mentions by Week</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={weekly_counts.reverse()}>
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
          {news_mentions.map((mention, idx) => (
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
