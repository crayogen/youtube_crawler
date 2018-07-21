import scrapy
from scrapy.crawler import CrawlerProcess
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import cPickle as pickle
import re
import time
import random
import pyperclip


def search_phrases(search_phrase_file):
    with open(search_phrase_file, 'r') as f:
        search_phrase = f.readlines()  # these are the words to search
    return ['https://www.youtube.com/results?search_query=' + x.strip().replace(' ', '+') for x in search_phrase]


class ProxySpider(scrapy.Spider):
    name = 'proxy'
    start_urls = ['http://spys.one/en/proxy-by-country/']
    proxy_pool = []
    no_of_pxy_countries = 10
    country_index = 0
    driver = None

    def __init__(self, *args, **kwargs):
    	# clear out start urls initially
    	# check to see if recent pickle file exists
    	# if so, just read it and return
    	# else open firefox and then call the super init
        if driver is None:
	        driver = webdriver.Firefox()
	    super(ProxySpider, self).__init__(*args, **kwargs)

    def parse(self, response):
        proxy_countries = response.xpath("//a[contains(@title, 'proxy servers list') and contains(@href, 'free-proxy-list')]/@href").extract()
        proxy_country_urls = ['http://spys.one' + proxy_country for proxy_country in proxy_countries]

        for proxy_country_url in proxy_country_urls[:self.no_of_pxy_countries]:
            print(proxy_country_url)
            time.sleep(3)
            yield self.parse_next(proxy_country_url)

    def parse_next(self, url):
        country_code = url[-3:-1]

        driver = self.driver
        driver.get(url=url)
        driver.find_element_by_xpath("//body").send_keys(Keys.CONTROL, "a")
        driver.find_element_by_xpath("//body").send_keys(Keys.CONTROL, "c")

        webpage_content = pyperclip.paste().encode('utf8')
        http_proxies = re.findall('(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,10})\t(HTTPS?)', webpage_content)

        self.proxy_pool.append([])
        if http_proxies is not None:
            for proxy in http_proxies:
                self.proxy_pool[self.country_index].append(proxy[1] + '://' + proxy[0])
            self.proxy_pool[self.country_index].append(country_code)
            self.country_index = self.country_index + 1

        print(self.proxy_pool)
        with open('../../my_proxies.txt', "wb") as f:
            pickle.dump(self.proxy_pool,  f)
            f.close()


class YoutubeSpider(scrapy.Spider):
    name = 'youtube'
    allowed_domains = ['youtube.com']
    delay = 3
    no_of_pgs_to_scrape = 2
    proxy_pool = []
    random.seed()

    def __init__(self, *args, **kwargs):
	    with open('../../my_proxies.txt', "rb") as file:
	    	# load this from proxyspider
	        self.proxy_pool = pickle.load(file)
	        file.close()
	    print(self.proxy_pool)
        super(YoutubeSpider, self).__init__(*args, **kwargs)

    def get_request(self, url, proxy_pool_index, page_number):
        req = scrapy.Request(url=url, callback=self.my_parse, errback=self.make_new_request, dont_filter=True)
        if self.proxy_pool:
            req.meta['proxy'] = random.choice(self.proxy_pool[proxy_pool_index][:-1])
            req.meta['proxy_pool_index'] = proxy_pool_index
            print('get request: {}'.format(proxy_pool_index))
        req.meta['dont_redirect'] = True
        req.meta['page_number'] = page_number
        return req

    def start_requests(self):
        print('our countries include: {}'.format(self.proxy_pool[proxy_pool_index][-1]))
        urls = search_phrases('../../read_file.txt')
        random.seed()
        for proxy_pool_index in range(0, len(self.proxy_pool)):
            for url in urls:
                print(proxy_pool_index)
                print(len(self.proxy_pool))
                print('and: {}'.format(self.proxy_pool[proxy_pool_index][-1]))
                yield self.get_request(url=url, proxy_pool_index=proxy_pool_index, page_number=1)
            # yield self.get_request(url=url, proxy_pool_index=proxy_pool_index, page_number=1)

    def make_new_request(self, failure):
        proxy_pool_index = failure.request.meta.get('proxy_pool_index')

        with open('../../errfile.txt', "a") as f:
            f.write(failure.request.url + ': ')
            f.write(repr(failure)+'\n')
        req = scrapy.Request(url=failure.request.url, callback=self.my_parse, errback=self.make_new_request, dont_filter=True)
        req.meta['proxy'] = random.choice(self.proxy_pool[proxy_pool_index][:-1])
        req.meta['proxy_pool_index'] = proxy_pool_index
        req.meta['dont_redirect'] = True
        req.meta['page_number'] = failure.request.meta.get('page_number')

        return req

    def my_parse(self, response):
        search_word = re.search('search_query=(.+?)(&|$)', response.url)  # searched for user input search term in the link i.e response.url
        search_word = search_word.group(1)
        proxy_pool_index = response.meta.get('proxy_pool_index')
        print('my parse: {}'.format(proxy_pool_index))
        country = self.proxy_pool[proxy_pool_index][-1]

        print(response.meta.get('proxy'))
        print(response.url)
        print("From country: {}".format(country))

        page_number = response.meta.get('page_number')

        filename = '../../yt_scraped_files/youtube_{}_{}.txt'.format(search_word, country)

        with open('../../yt_scraped_files/scraped_urls.txt', "a") as my_file:
                my_file.write(response.url + '\n')
                my_file.close()

        youtube_vid_urls = response.xpath("//a[contains(@href, 'watch') and @aria-hidden='true']/@href").extract() # found all the urls on the nth page

        for s in youtube_vid_urls[1:]:  # wrote all the scraped urls in a file
            with open(filename, "a") as my_file:
                my_file.write('https://www.youtube.com' + s + '\n')
                my_file.close()

        yt_nextpage_codes = '../../codes.txt'
        with open(yt_nextpage_codes, 'r') as f:
            next_pages_urls = ['https://www.youtube.com/results?search_query=' + search_word + f.strip() for f in f.readlines()]

        # this is to ensure that the response os the next pages are in the correct order
        if page_number < self.no_of_pgs_to_scrape:
            print("lis of urls: {}".format(next_pages_urls))
            print("the list is {} long".format(len(next_pages_urls)))
            if page_number is None:
                print("trynna acces this: {}".format(page_number-1))
            next_page_url = next_pages_urls[page_number-1]
            if proxy_pool_index is None or next_page_url is None:
                print('stop')
            yield self.get_request(url=next_page_url, proxy_pool_index=proxy_pool_index, page_number=page_number+1)

if __name__ == '__main__':
	process = CrawlerProcess()

	process.crawl(ProxySpider)
#	process.crawl(YoutubeSpider)

	process.start()
