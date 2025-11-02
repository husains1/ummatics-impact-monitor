import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os
import sys

# Add parent directory to path to import ingestion module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ingestion import run_full_ingestion

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
    scheduler.add_job(
        scheduled_ingestion,
        trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
        id='weekly_ingestion',
        name='Weekly Data Ingestion',
        replace_existing=True
    )
    
    logger.info("Scheduler configured:")
    logger.info("  - Weekly data ingestion: Every Monday at 9:00 AM")
    logger.info("=" * 60)
    
    # Run initial ingestion on startup
    logger.info("Running initial data ingestion...")
    scheduled_ingestion()
    
    try:
        logger.info("Scheduler is now running. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutdown requested")
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
