import logging
import os


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_massive_api_key():
    # MASSIVE_API_KEY environment variable takes precedence over POLYGON_API_KEY
    logger.info("Getting Massive API key...")
    api_key = os.environ.get("MASSIVE_API_KEY")

    # If MASSIVE_API_KEY is not set, try POLYGON_API_KEY
    if not api_key:
        logger.info("MASSIVE_API_KEY environment variable not set; trying POLYGON_API_KEY...")
        api_key = os.environ.get("POLYGON_API_KEY")

    # If POLYGON_API_KEY is not set, try reading from file
    if not api_key:
        logger.info("POLYGON_API_KEY environment variable not set; trying Massive API key file...")
        api_key_path = '/app/massive_api_key.txt'
        try:
            with open(api_key_path, 'r') as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            logger.info(f"No Massive API key file found at {api_key_path}")

    # Raise error if neither POLYGON_API_KEY nor MASSIVE_API_KEY are set
    if not api_key:
        logger.error("No Massive API key found")
        raise ValueError("MASSIVE_API_KEY environment variable not set")
    logger.info("Done.")
    return api_key
