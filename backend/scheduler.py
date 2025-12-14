import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os
import sys

# Add parent directory to path to import ingestion module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ingestion import run_full_ingestion
from ingestion import update_sentiment_metrics
from ingestion import google_search_subreddits
from ingestion import cleanup_citations
from datetime import date, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scheduled_ingestion():
    """Wrapper function for scheduled ingestion with error handling"""
    try:
        logger.info("Starting scheduled data ingestion...")
        # Run citation cleanup before ingestion to remove dead URLs and duplicates
        cleanup_citations()
        run_full_ingestion()
        logger.info("Scheduled data ingestion completed successfully")
    except Exception as e:
        logger.error(f"Error in scheduled ingestion: {e}")


def main():
    """Main scheduler function"""
    logger.info("=" * 60)
    logger.info("Ummatics Impact Monitor - Scheduler Starting")
    logger.info("=" * 60)
    
    scheduler = BlockingScheduler()
    
    # Schedule ingestion every Monday at 9:00 AM
    #scheduler.add_job(
        #scheduled_ingestion,
        #trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
        #id='weekly_ingestion',
        #name='Weekly Data Ingestion',
        #replace_existing=True
    #)
    
    # Schedule ingestion 3x daily (8 AM, 2 PM, 8 PM UTC) to stay within Twitter's 100 posts/month limit
    # With 3 runs/day * 30 days = 90 API calls/month (safely under 100 limit)
    scheduler.add_job(
        scheduled_ingestion,
        trigger=CronTrigger(hour='8,14,20', minute=0),
        id='three_daily_ingestion',
        name='3x Daily Data Ingestion',
        replace_existing=True
    )

    logger.info("Scheduler configured:")
    logger.info("  - Data ingestion: 3x daily at 8 AM, 2 PM, 8 PM UTC (Twitter quota optimization)")
    logger.info("=" * 60)
    
    # Run initial ingestion on startup
    logger.info("Running initial data ingestion...")
    scheduled_ingestion()
    # Run initial sentiment update for recent days
    def scheduled_sentiment():
        try:
            logger.info("Starting scheduled sentiment update for recent days...")
            today = datetime.now().date()
            # update sentiment metrics for the last 7 days (inclusive)
            for i in range(0, 7):
                d = today - timedelta(days=i)
                update_sentiment_metrics(d)
            logger.info("Scheduled sentiment update completed")
        except Exception as e:
            logger.error(f"Error in scheduled sentiment update: {e}")

    # Schedule sentiment update 3x daily at :30 (shortly after each ingestion)
    scheduler.add_job(
        scheduled_sentiment,
        trigger=CronTrigger(hour='8,14,20', minute=30),
        id='three_daily_sentiment',
        name='3x Daily Sentiment Update',
        replace_existing=True
    )
    
    # Schedule Google subreddit discovery once per week (Sunday at 10:00 AM)
    def scheduled_google_subreddit_discovery():
        try:
            logger.info("Starting scheduled Google subreddit discovery...")
            new_subreddits = google_search_subreddits()
            if new_subreddits:
                logger.info(f"Google discovery found {len(new_subreddits)} new subreddits: {', '.join(new_subreddits)}")
            else:
                logger.info("No new subreddits found via Google search")
        except Exception as e:
            logger.error(f"Error in scheduled Google subreddit discovery: {e}")
    
    scheduler.add_job(
        scheduled_google_subreddit_discovery,
        trigger=CronTrigger(day_of_week='sun', hour=10, minute=0),
        id='weekly_google_subreddit_discovery',
        name='Weekly Google Subreddit Discovery',
        replace_existing=True
    )
    
    logger.info("Additional scheduled jobs:")
    logger.info("  - Weekly Google subreddit discovery: Every Sunday at 10:00 AM")
    
    try:
        logger.info("Scheduler is now running. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutdown requested")
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
