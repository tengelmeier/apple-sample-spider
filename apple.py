# apple.py

import scrapy
from scrapy_splash import SplashRequest
import re

class AppleSpider(scrapy.Spider):
    name = 'apple'
    allowed_domains = ['developer.apple.com']
    start_urls = ['https://developer.apple.com/documentation/']

    def start_requests(self):
        for url in self.start_urls:
            yield SplashRequest(url, callback=self.parse)

    def parse(self, response):
        # Beispiel-Regex für die Links zu Sample Code
        pattern = re.compile(r'/documentation/\w+/.+\.js')
        
        # Sucht nach den Links und gibt sie aus
        for link in response.css('a::attr(href)').re(pattern):
            full_url = 'https://developer.apple.com' + link
            self.logger.info(f'Found Sample Code: {full_url}')
            
            # Du kannst hier den Link in einer Datei speichern oder weiter verarbeiten
