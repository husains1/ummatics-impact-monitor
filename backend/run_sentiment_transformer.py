"""One-off runner to analyze missing sentiment on existing social_mentions.

This script scans `social_mentions` for rows with NULL or missing `sentiment`
and computes sentiment using the project's `analyze_sentiment` function
from `ingestion.py` (which falls back to TextBlob if transformers are not
installed). After updating rows it calls `update_sentiment_metrics` for each
affected date to populate `social_sentiment_metrics`.

Run inside the project with the same env as other services, for example:
  docker-compose run --rm api python backend/run_sentiment_transformer.py
"""
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from ingestion import get_db_connection, analyze_sentiment, update_sentiment_metrics


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Find mentions missing sentiment
    cur.execute("SELECT id, content, posted_at::date FROM social_mentions WHERE sentiment IS NULL OR sentiment_analyzed_at IS NULL")
    rows = cur.fetchall()
    if not rows:
        logger.info("No social mentions missing sentiment analysis.")
        cur.close()
        conn.close()
        return

    logger.info(f"Found {len(rows)} mentions missing sentiment. Processing...")

    # Track unique dates we update so we can refresh daily metrics
    dates_touched = set()

    for r in rows:
        try:
            mid, content, posted_date = r
            sentiment, score = analyze_sentiment(content)
            cur.execute("UPDATE social_mentions SET sentiment = %s, sentiment_score = %s, sentiment_analyzed_at = %s WHERE id = %s",
                        (sentiment, score, datetime.utcnow(), mid))
            dates_touched.add(posted_date)
        except Exception as e:
            logger.error(f"Error updating sentiment for id {r[0]}: {e}")
            continue

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Updated sentiment for {len(rows)} mentions. Updating daily sentiment metrics for {len(dates_touched)} dates...")
    for d in sorted(dates_touched):
        try:
            update_sentiment_metrics(d)
        except Exception as e:
            logger.error(f"Error updating sentiment metrics for {d}: {e}")

    logger.info("Sentiment run complete.")


if __name__ == '__main__':
    main()
