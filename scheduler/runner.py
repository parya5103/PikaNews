import os
import sys
import asyncio
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

# Add parent directory to path to ensure modules are importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.coordinator import ScrapeCoordinator

logger = structlog.get_logger(__name__)

def load_config() -> dict:
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not os.path.exists(config_path):
        logger.error("Configuration file not found", path=config_path)
        sys.exit(1)
        
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

async def run_scrape_job(source_name: str, coordinator: ScrapeCoordinator):
    """Executes a scraping process block for the specified source."""
    logger.info("Executing scheduled job", source=source_name)
    try:
        results = await coordinator.scrape_source(source_name)
        logger.info("Scheduled job finished", source=source_name, results=results)
    except Exception as e:
        logger.error("Scheduled job failed", source=source_name, error=str(e))

async def main():
    config = load_config()
    
    # Initialize coordinator
    coordinator = ScrapeCoordinator(config)
    await coordinator.initialize_pipelines()
    
    scheduler = AsyncIOScheduler()
    
    sources = config.get("sources", [])
    if not sources:
        logger.warn("No sources configured to schedule. Exiting.")
        return

    # Standard stagger delta (seconds) to prevent concurrency spike on boot
    stagger_seconds = 0

    for source in sources:
        name = source["name"]
        cron = source.get("schedule_cron", "0 * * * *")  # Default hourly
        
        logger.info("Registering scrape job", source=name, cron=cron)
        
        # Schedule cron job
        scheduler.add_job(
            run_scrape_job,
            CronTrigger.from_crontab(cron),
            args=[name, coordinator],
            id=f"scrape_{name}",
            replace_existing=True
        )
        
        # Run an initial scrape after a staggered delay if requested
        stagger_seconds += 10

    # Start APScheduler
    logger.info("Starting scheduler loop...")
    scheduler.start()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down...")
    finally:
        await coordinator.close_pipelines()

if __name__ == "__main__":
    # Ensure logs format cleanly
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    asyncio.run(main())
