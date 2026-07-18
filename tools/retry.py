import asyncio
import logging

logger = logging.getLogger(__name__)


async def retry(func, retries=3, delay=2, name=""):
    for attempt in range(retries):
        try:
            return await func()
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(
                    "%s failed (attempt %d/%d): %s. Retrying in %ds...",
                    name, attempt + 1, retries, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("%s failed after %d attempts: %s", name, retries, e)
                raise
