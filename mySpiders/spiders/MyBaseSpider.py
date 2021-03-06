# -*- coding: utf-8 -*-
import re

import urlparse
from scrapy.http import Request
from scrapy.spiders import Spider
import mySpiders.utils.log as logging

from config import REFERER, OPEN_REDIS_DISTINCT
from mySpiders.utils.http import requstDistinct
from mySpiders.utils.hash import toMd5


import sys
reload(sys)
sys.setdefaultencoding("utf8")


class MyBaseSpider(Spider):

    img_pattern = re.compile(r'<\s*?img.*?src\s*?=\s*?[\'"](.*?)[\'"].*?\>', re.M | re.S)
    text_pattern = re.compile(r'<\s*?(.*?)\>|[\s\n]', re.M | re.S)
    url_domain_pattern = re.compile(r'$http://.*?', re.M | re.S)
    num_pattern = re.compile(r'\d+', re.M | re.S)

    def __init__(self, *arg, **argdict):
        """ 初始化对象属性 """

        self.rule = ''
        self.titleXpath = ''
        self.descriptionXpath = ''
        self.descriptionLenght = 0
        self.contentXpath = ''
        self.linkXpath = ''
        self.imgUrlXpath = ''
        self.imageNum = 0
        self.goodRemarkXpath = ''
        self.badRemarkXpath = ''
        self.zhunfaRemarkXpath = ''

        self.videoUrlXpath = ''
        self.pubDateXpath = ''
        self.guidXpath = ''
        self.rule_id = ''
        self.checkTxtXpath = ''
        self.max_deepth = 0
        self.is_duplicate = False
        self.last_md5 = ''
        self.next_request_url = ''
        self.next_page_url_prefix = ''
        Spider.__init__(self, *arg, **argdict)
        self.currentNode = None
        self.isDone = False
        self.isFirstListPage = True

    def initConfig(self, spiderConfig):
        """initing"""

        self.rule = spiderConfig.get('rule', '')
        self.titleXpath = spiderConfig.get('title_node', '')
        self.descriptionXpath = spiderConfig.get('description_node', '')
        self.descriptionLenght = int(spiderConfig.get('description_length', 255))
        if self.descriptionLenght < 1 or self.descriptionLenght > 255:
            self.descriptionLenght = 255

        self.contentXpath = spiderConfig.get('content_node', '')
        self.linkXpath = spiderConfig.get('guid_node', '')
        self.imgUrlXpath = spiderConfig.get('img_node', '')
        self.imageNum = int(spiderConfig.get('img_num', 0))

        self.goodRemarkXpath = spiderConfig.get('good_remark_node', '')
        self.badRemarkXpath = spiderConfig.get('bad_remark_node', '')
        self.zhunfaRemarkXpath = spiderConfig.get('zhuafa_node', '')

        self.videoUrlXpath = spiderConfig.get('video_node', '')
        self.pubDateXpath = spiderConfig.get('public_time', '')
        self.guidXpath = spiderConfig.get('guid_node', '')

        # logging.info("--------guid_node---%s---------------" % self.guidXpath)
        self.rule_id = spiderConfig.get('id', '')
        self.is_duplicate = spiderConfig.get('is_duplicate', 0)
        self.checkTxtXpath = spiderConfig.get('check_area_node', '//body')
        self.last_md5 = spiderConfig.get('last_md5', '')
        self.max_deepth = int(spiderConfig.get('max_deepth', -1))
        if self.max_deepth < 1:
            self.max_deepth = 500

        self.next_request_url = spiderConfig.get('next_request_url', '')
        self.next_page_url_prefix = spiderConfig.get('next_page_url_prefix', '')

    def getNextListPageUrl(self, response):

        requestUrl = []
        self.max_deepth -= 1
        if self.max_deepth < 1:
            logging.info("*********max_deepth : %s   *****" % self.max_deepth)
            return requestUrl

        # logging.info("*********next_request_url : %s   *****" % self.next_request_url)
        nextListPageURL = self.safeParse(response, self.next_request_url)

        # logging.info("*********next_page_url_prefix : %s   *****" % self.next_page_url_prefix)
        if self.next_page_url_prefix:
            nextListPageURL = self.appendDomain(nextListPageURL, self.next_page_url_prefix, False)
        else:
            nextListPageURL = self.appendDomain(nextListPageURL, response.url)

        logging.info("*********nextListPageURL : %s   *****" % nextListPageURL)

        if nextListPageURL:
            requestUrl.append(
                Request(nextListPageURL, headers={'Referer': REFERER}, callback=self.parse, dont_filter=True))
        return requestUrl

    def getDetailPageUrls(self, response):

        detailUrls = [self.appendDomain(t.encode('utf-8'), response.url)
                      for t in self.safeParse(response, self.rule, True, False)]

        # 批量验证urls是否重复
        logging.info("*********detailUrls : %s   *****" % detailUrls)
        detailUrlsByFilter = self.distinctRequestUrls(detailUrls)
        logging.info("*********detailUrlsByFilter : %s   *****" % detailUrlsByFilter)

        if len(detailUrls) < 1 or len(detailUrlsByFilter) != len(detailUrls):
            self.isDone = True

        requestUrl = []
        if detailUrlsByFilter:
            for detailUrl in detailUrlsByFilter:
                requestUrl.append(
                    Request(detailUrl, headers={'Referer': REFERER}, callback=self.parse_detail_page, dont_filter=True))
        return requestUrl

    def appendDomain(self, url, domain='', is_parse=True):

        if not is_parse:
            return domain + url

        parsed_uri = urlparse.urlparse(domain)
        domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
        logging.info("*********apend before : %s   *****" % url)
        if isinstance(url, (buffer, str)) and not self.url_domain_pattern.match(url):
            url = urlparse.urljoin(domain, url)
        return url

    def distinctRequestUrls(self, urls):

        if len(urls) < 1:
            return []

        if (not OPEN_REDIS_DISTINCT) or self.is_duplicate:
            return list(urls)

        uniqueCodeDict = {}
        for url in urls:
            uniqueCodeDict[toMd5(url)] = url

        repeatUniqueCode = requstDistinct(uniqueCodeDict.keys())
        for i, unique in enumerate(repeatUniqueCode):
            del(uniqueCodeDict[unique])
        return uniqueCodeDict.values()

    def safeParse(self, response, xpathPattern, isMutile=False, isUtf8=True):
        """safe about extract datas"""

        if not xpathPattern:
            return ([] if isMutile else "")

        if isMutile:
            if isUtf8:
                return [(t.encode('utf-8') if t else t) for t in response.xpath(xpathPattern).extract()]
            else:
                return response.xpath(xpathPattern).extract()
        else:
            if isUtf8:
                tmp = response.xpath(xpathPattern).extract_first()
                return (tmp.encode('utf-8') if tmp else tmp)
            else:
                return response.xpath(xpathPattern).extract_first()

    def parseContentAndImages(self, response):

        if not self.imgUrlXpath:
            content = self.safeParse(response, self.contentXpath)
            imgUrlList = self.__parseImg(content,response.url)
        else:
            content = self.safeParse(response, self.contentXpath)
            imgUrlList = [ self.appendDomain(url,response.url) for url in self.safeParse(response, self.imgUrlXpath, True) ]

        return {"img_url": imgUrlList, "content": content}

    def parseDescription(self, text):
        """调用此方法获取description"""

        description = self.safeParse(response, self.descriptionXpath) if self.descriptionXpath else text
        txt = self.text_pattern.sub('', description)
        if not txt:
            return ""
        return txt.decode('utf8')[0:self.descriptionLenght].encode('utf8')

    def __parseImg(self, text,domain):
        """当img_node不存在是，调用此方法获取img_url数据"""

        imgUrlsList = []
        if not text:
            return imgUrlsList

        imgUrls = self.img_pattern.findall(text)

        if not imgUrls:
            return imgUrlsList

        if self.imageNum:
            imgUrlsList = imgUrls[0:self.imageNum]

        resultUrlList = []
        for imgurl in imgUrlsList:
            resultUrlList.append(self.appendDomain(imgurl,domain))

        return resultUrlList

    def parseNum(self,string):
        """解析字符串获取数字"""

        num = 0
        r = self.num_pattern.search(string)
        if r:
            num = r.group()
        return num