import logging
import os


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_massive_api_key():
    logger.info("Getting Massive API key...")
    api_key = os.environ.get("MASSIVE_API_KEY")
    if not api_key:
        logger.info("MASSIVE_API_KEY environment variable not set; trying Massive API key...")
        api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        logger.info("POLYGON_API_KEY environment variable not set; trying Massive API key file...")
        api_key_path = '/app/polygon_api_key.txt'
        with open(api_key_path, 'r') as f:
            api_key = f.read().strip()
    if not api_key:
        logger.error("No Massive API key found")
        raise ValueError("MASSIVE_API_KEY environment variable not set")
    logger.info("Done.")
    return api_key
