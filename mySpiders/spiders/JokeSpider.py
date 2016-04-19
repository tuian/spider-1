# -*- coding: utf-8 -*-
# import re

from scrapy.http import Request
from mySpiders.spiders.MyBaseSpider import MyBaseSpider
import mySpiders.utils.log as logging
from mySpiders.items import JokeItem

from mySpiders.utils.http import getCrawlRequest, syncLastMd5
from mySpiders.utils.hash import toMd5
from config import REFERER


class JokeSpider(MyBaseSpider):

    name = 'JokeSpider'

    start_urls = []

    custom_settings = {
        'ITEM_PIPELINES': {
            'mySpiders.pipelines.JokePipeline': 1
        }
    }

    next_request_url_prefix = 'http://www.budejie.com/text/'

    def start_requests(self):

        spiderConfig = getCrawlRequest()
        if not spiderConfig:
            return []

        self.initConfig(spiderConfig)
        logging.info("*********meta******%s****************" % spiderConfig)
        return [Request(spiderConfig.get('start_urls', '')[0], callback=self.parse, dont_filter=True)]

    def parse(self, response):
        """ 列表页解析 """

        last_md5 = ''
        if self.isFirstListPage:
            checkText = self.safeParse(response, self.checkTxtXpath)
            last_md5 = toMd5(checkText)

        logging.info("*********last_md5 : %s   self.last_md5 : %s*****" % (last_md5, self.last_md5))
        if self.isFirstListPage and last_md5 == self.last_md5:
            yield []
        else:
            for request in self.getDetailPageUrls(response):
                yield request

            # 获取下一列表页url
            if not self.isDone:
                for request in self.getNextListPageUrl(response):
                    request = self.appendDomain(request, self.next_request_url_prefix, False)
                    yield Request(request, headers={'Referer': REFERER}, callback=self.parse, dont_filter=True)

            # 同步md5码 & 同步last_id
            if self.isFirstListPage:
                syncLastMd5({'last_md5': last_md5, 'id': self.rule_id})

        self.isFirstListPage = False

    def parse_detail_page(self, response):

        logging.info('--------------------parse detail page-----------')
        item = JokeItem()
        item['title'] = self.safeParse(response, self.titleXpath)

        imageAndDescriptionInfos = self.parseDescriptionAndImages(response)
        item['img_url'] = imageAndDescriptionInfos['img_url']
        item['description'] = imageAndDescriptionInfos['description']

        # item['public_time'] = self.safeParse(response, self.pubDateXpath)
        item['source_url'] = response.url
        item['rule_id'] = self.rule_id
        yield item
