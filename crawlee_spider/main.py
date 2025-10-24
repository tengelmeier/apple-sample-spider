from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.http_clients import ImpitHttpClient
# from .routes import router
from crawlee.storages import KeyValueStore, Dataset
from crawlee.configuration import Configuration
from crawlee import Glob
import asyncio
import httpx

async def main():
    """The crawler entry point."""
    # Set the purge_on_start field to False to avoid purging the storage on start.
    configuration = Configuration(purge_on_start=False)

    crawler = PlaywrightCrawler(
        # request_handler=router,
        headless=True,
        configuration=configuration,
        max_requests_per_crawl=700,
        http_client=ImpitHttpClient(),
    )
    kv_store = await KeyValueStore.open(configuration=configuration, name="samplecode")
    dataset = await Dataset.open(configuration=configuration, name="samplecode")

    # THe Client will be used to download the real sample code
    client = httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"})

    # Create single httpx client for reuse
    # async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
    @crawler.router.handler(label='detail')
    async def detail_handler(context: PlaywrightCrawlingContext) -> None:
        context.log.info(f'Detail page {context.request.url} ...')

        # We're not processing detail pages yet, so we just pass.
        await context.page.wait_for_selector('.main a.sample-download')
        link = await context.page.query_selector('.main a.sample-download')
        code_uri = await link.get_attribute('href')
        file_name = code_uri.split("/")[-1]
        if await kv_store.record_exists(file_name):
            context.log.info(f'Skipping already downloaded: {file_name}')
            return

        context.log.info(f'=> {code_uri}')

        try:
            response = await client.get(code_uri)
            response.raise_for_status()

            # Get file extension from Content-Type
            content_type = response.headers.get("Content-Type", "application/binary")
            # file_extension = content_type.split("/")[-1].split(";")[0]
           
            # Persist result in KeyValueStore
            await kv_store.set_value(file_name, response.content, content_type=content_type)
            context.log.info(f"Stored: {file_name}")

            # Store metadata in Dataset
            dataset_entry = {
                "code_url": code_uri,
                "file_key": file_name,
                "source_page": context.request.url
            }
            await dataset.push_data(dataset_entry)

        except httpx.HTTPError as e:
            context.log.error(f"Failed to download {code_uri}: {e}")


        #await context.enqueue_links(
        #    include=[Glob('https://docs-assets.developer.apple.com/**/*.zip')],
        #    label='samplecode'
        #)

    @crawler.router.default_handler
    async def default_handler(context: PlaywrightCrawlingContext) -> None:
        """Default request handler."""
        context.log.info(f'Processing {context.request.url} ...')
        title = await context.page.query_selector('title')

        await context.page.wait_for_selector('.doc-content')

        links = await context.page.query_selector('.doc-content > a')

        # Enqueue links that match the 'include' glob pattern and
        # do not match the 'exclude' glob pattern.
        await context.enqueue_links(
            include=[Glob('https://developer.apple.com/documentation/**')],
            label='detail'
        )

        if links:
            links = [await link.get_attribute('href') for link in links]
            await context.push_data(
                {
                    'url': context.request.loaded_url,
                    'title': await title.inner_text() if title else None,
                    'links': links
                }
            )

    await crawler.run(
        [
            'https://developer.apple.com/documentation/samplecode',
        ]
    )

