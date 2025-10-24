from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router
from crawlee import Glob

router = Router[PlaywrightCrawlingContext]()


@router.default_handler
async def default_handler(context: PlaywrightCrawlingContext) -> None:
    """Default request handler."""
    context.log.info(f'Processing {context.request.url} ...')
    title = await context.page.query_selector('title')
    
    if context.request.label == None:
        await context.page.wait_for_selector('.doc-content')

        links = await context.page.query_selector('.doc-content > a')
    
        # Enqueue links that match the 'include' glob pattern and
        # do not match the 'exclude' glob pattern.
        await context.enqueue_links(
            include=[Glob('https://developer.apple.com/documentation/**')],
            label='detail'
        )

        await context.push_data(
            {
               'url': context.request.loaded_url,
               'title': await title.inner_text() if title else None,
               'links': links
            }
        )


        

       


