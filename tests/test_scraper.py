import pytest
from eitaa_scraper import EitaaScraper

@pytest.mark.asyncio
async def test_login():
    async with EitaaScraper() as scraper:
        assert await scraper.is_logged_in() 