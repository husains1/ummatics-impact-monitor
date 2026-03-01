-- Ummatics Impact Monitor Database Schema

-- Weekly snapshots for overview data
CREATE TABLE weekly_snapshots (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL UNIQUE,
    week_end_date DATE NOT NULL,
    total_news_mentions INTEGER DEFAULT 0,
    total_social_mentions INTEGER DEFAULT 0,
    total_citations INTEGER DEFAULT 0,
    total_website_sessions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Social media platform metrics (weekly)
CREATE TABLE social_media_metrics (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    follower_count INTEGER DEFAULT 0,
    mentions_count INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week_start_date, platform)
);

-- Social media platform metrics (daily)
CREATE TABLE IF NOT EXISTS social_media_daily_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    follower_count INTEGER DEFAULT 0,
    mentions_count INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, platform)
);

-- Social media sentiment metrics (daily)
CREATE TABLE IF NOT EXISTS social_sentiment_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    unanalyzed_count INTEGER DEFAULT 0,
    average_sentiment_score DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, platform)
);

-- Individual social media mentions
CREATE TABLE social_mentions (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    post_id VARCHAR(255) UNIQUE,
    author VARCHAR(255),
    content TEXT,
    post_url TEXT,
    posted_at TIMESTAMP,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    sentiment VARCHAR(20),
    sentiment_score DECIMAL(5, 2),
    sentiment_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Website analytics metrics
CREATE TABLE website_metrics (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL UNIQUE,
    total_sessions INTEGER DEFAULT 0,
    total_users INTEGER DEFAULT 0,
    total_pageviews INTEGER DEFAULT 0,
    avg_session_duration DECIMAL(10, 2) DEFAULT 0,
    bounce_rate DECIMAL(5, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Top performing pages
CREATE TABLE top_pages (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    page_path TEXT NOT NULL,
    pageviews INTEGER DEFAULT 0,
    avg_time_on_page DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week_start_date, page_path)
);

-- Geographic distribution of visitors
CREATE TABLE geographic_metrics (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    country VARCHAR(100) NOT NULL,
    sessions INTEGER DEFAULT 0,
    users INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week_start_date, country)
);

-- Academic citations
CREATE TABLE citations (
    id SERIAL PRIMARY KEY,
    work_id VARCHAR(255) UNIQUE,
    doi VARCHAR(255),
    title TEXT NOT NULL,
    authors TEXT,
    publication_date DATE,
    cited_by_count INTEGER DEFAULT 0,
    source_url TEXT,
    is_dead BOOLEAN DEFAULT FALSE,
    citation_type VARCHAR(20) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weekly citation metrics
CREATE TABLE citation_metrics (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL UNIQUE,
    total_citations INTEGER DEFAULT 0,
    new_citations_this_week INTEGER DEFAULT 0,
    total_works INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- News mentions from Google Alerts
CREATE TABLE news_mentions (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source VARCHAR(255),
    published_at TIMESTAMP,
    snippet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(url, title)
);

-- Discovered subreddits for automated monitoring
CREATE TABLE IF NOT EXISTS discovered_subreddits (
    id SERIAL PRIMARY KEY,
    subreddit_name VARCHAR(255) UNIQUE NOT NULL,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_weekly_snapshots_date ON weekly_snapshots(week_start_date);
CREATE INDEX idx_social_media_metrics_date ON social_media_metrics(week_start_date);
CREATE INDEX idx_social_mentions_date ON social_mentions(week_start_date);
CREATE INDEX idx_website_metrics_date ON website_metrics(week_start_date);
CREATE INDEX idx_top_pages_date ON top_pages(week_start_date);
CREATE INDEX idx_geographic_metrics_date ON geographic_metrics(week_start_date);
CREATE INDEX idx_citation_metrics_date ON citation_metrics(week_start_date);
CREATE INDEX idx_news_mentions_date ON news_mentions(week_start_date);
