from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.http_clients import ImpitHttpClient
# from .routes import router
from crawlee.storages import KeyValueStore, Dataset
from crawlee.configuration import Configuration
from crawlee import Glob
from crawlee import Request
import asyncio
import tracemalloc
import httpx

async def main():
    """The crawler entry point."""
    # Set the purge_on_start field to False to avoid purging the storage on start.
    no_purge_configuration = Configuration(purge_on_start=False)

    crawler = PlaywrightCrawler(
        # request_handler=router,
        headless=True,
        # configuration=no_purge_configuration,
        max_requests_per_crawl=700,
        http_client=ImpitHttpClient(),
    )
    sample_stores = {}
    sample_metadata_store = await Dataset.open(configuration=no_purge_configuration, name="samplecode")

    # hack. ReqestQueue based deduplication does not work and the Crawler leaks like hell
    index_store = await KeyValueStore.open(configuration=no_purge_configuration, name="index")

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        @crawler.router.handler(label='detail')
        async def detail_handler(context: PlaywrightCrawlingContext) -> None:
            context.log.info(f'Detail page {context.request.url} ...')
            # We're not processing detail pages yet, so we just pass.
            await context.page.wait_for_selector('.main a.sample-download')
            html_platforms = await context.page.query_selector_all('.main span.platform')
            platforms = [await p.inner_text() for p in html_platforms] if html_platforms else []

            if (link := await context.page.query_selector('.main a.sample-download')) and (code_uri := await link.get_attribute('href')):
                file_name = code_uri.split("/")[-1]
                category = context.request.url.split('/')[-2]  # crude category extraction

### move to back later
                store = sample_stores.get(category, await KeyValueStore.open(configuration=no_purge_configuration, name=category))
                sample_stores[category] = store

                if await store.record_exists(file_name):
                    await index_store.set_value(context.request.url.split('/')[-1], file_name, content_type='application/text')
                    context.log.info(f"Already stored: {file_name}")
                    return  
        
                context.log.info(f'=> {code_uri}')
                try:
                    response = await client.get(code_uri)
                    response.raise_for_status()
                
                    # Store metadata in Dataset
                    dataset_entry = {
                        "code_url": code_uri,
                        "file": file_name,
                        "relative_file": f"{category}/{file_name}",
                        "page_url": context.request.url,
                        "platforms": platforms,
                    }
                    await sample_metadata_store.push_data(dataset_entry)

                    # Persist result in KeyValueStore
                    content_type = response.headers.get("Content-Type", "application/binary")
                    await store.set_value(file_name, response.content, content_type=content_type)

                    # exclude from reindexing:
                    await index_store.set_value(context.request.url.split('/')[-1], file_name, content_type='application/text')
                    context.log.info(f"Stored: {file_name}")


                except httpx.HTTPError as e:
                    context.log.error(f"Failed to download {code_uri}: {e}")

        def profile_memory():
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            print("[ Top 10 ]")
            for stat in top_stats[:10]:
                print(stat)

        #await context.enqueue_links(
        #    include=[Glob('https://docs-assets.developer.apple.com/**/*.zip')],
        #    label='samplecode'
        #)

        @crawler.router.default_handler
        async def default_handler(context: PlaywrightCrawlingContext) -> None:
            """Default request handler (only for index)."""
            context.log.info(f'Processing {context.request.url} ...')
            title = await context.page.query_selector('title')

            await context.page.wait_for_selector('.doc-content')

            my_links = await context.page.query_selector_all('.doc-content > a')

             # Extract all the documentation links found on the page, except for the examples.
            extracted_links = await context.extract_links(
                include=[Glob('https://developer.apple.com/documentation/**')],
                exclude=[Glob('https://developer.apple.com/documentation/samplecode?')],
            )
            # Some very custom filtering which can't be achieved by `extract_links` arguments.
            filtered_links = [
                link for link in extracted_links if not await index_store.record_exists(link.url.split('/')[-1])  
            ]
            # Add filtered links to the request queue.
            await context.add_requests([Request.from_url(url=link.url, label='detail') for link in filtered_links])

            # Enqueue links that match the 'include' glob pattern and
            # do not match the 'exclude' glob pattern.
            # await context.enqueue_links(
            #    include=[Glob('https://developer.apple.com/documentation/**')],
            #    label='detail'
            # )

            if my_links:
                links = [await link.get_attribute('href') for link in my_links]
                await context.push_data(
                    {
                        'url': context.request.loaded_url,
                        'title': await title.inner_text() if title else None,
                        'links': links
                    }
                )

        tracemalloc.start()
        await crawler.run(
            [
                'https://developer.apple.com/documentation/samplecode',
            ]
        )
