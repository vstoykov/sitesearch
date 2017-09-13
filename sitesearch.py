#!/usr/bin/env python3
import argparse
import logging
import threading
import queue

import requests
from lxml import etree


SITEMAP_NAMESPACE = 'http://www.sitemaps.org/schemas/sitemap/0.9'
XMLNS = {'sitemap': SITEMAP_NAMESPACE}

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

VERBOSE_HELP = (
    """Verbose mode. Controls the script output
    0 - print output only in case of errors
    1 - prints the result count plus list of failed URLs(if any)
    2 - print all checked URLs \n""")

LOGGING_LEVELS = {
    0: logging.ERROR,
    1: logging.INFO,
    2: logging.DEBUG,
}


logger = logging.getLogger(__name__)


def iter_sitemap_urls(url):
    """
    Accept URL address that will be parsed as a sitemap.
    Yelds URL addresses from the sitemap.
    If sitemap is an index then open each sitemap in the index
    and yeeld the URLs from there.
    """
    try:
        tree = etree.parse(url)
    except OSError:
        # lxml cant't fetch the URL. Fallback with requests
        response = requests.get(url)
        root = etree.fromstring(response.content)
    else:
        root = tree.getroot()

    if root.tag.endswith('sitemapindex'):
        logger.debug('Processing sitemap index: %s', url)
        for sitemap in root:
            sitemap_url = sitemap.find('sitemap:loc', namespaces=XMLNS).text
            logger.debug('Sitemap URL: %s', sitemap_url)
            for item in iter_sitemap_urls(sitemap_url):
                yield item
    elif root.tag.endswith('urlset'):
        logger.debug('Processing sitemap: %s', url)
        for url in root:
            loc = url.find('sitemap:loc', namespaces=XMLNS).text.strip()
            logger.debug('Location: %s', loc)
            yield loc
    else:
        raise ValueError('Invalid sitemap')


def iter_search_in_urls(urls, search_string):
    """
    Accepts iterable of urls and search string.
    Yelds urls in which the given search string was found and the number
    of ocurances of that string in the given url.
    """
    with requests.session() as session:
        for url in urls:
            response = session.get(url)
            count = response.text.count(search_string)
            if count:
                logger.info('Search string found %d time(s) in %s', count, url)
                yield url, count


def search_in_site(sitemap_url, search_string, concurency=4):
    """
    Concurently iterate over URLs in a sitemap and search for string.
    Return iterator with the results.
    Every result is a tuple of url and number of occurrences
    """
    q = queue.Queue()
    threads = []
    items = safeiter(iter_sitemap_urls(sitemap_url))

    def worker(items, q):
        for item in iter_search_in_urls(items, search_string):
            q.put(item)

    for i in range(concurency):
        thread = threading.Thread(target=worker, args=(items, q))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    q.put(StopIteration)

    return iter(q.get, StopIteration)


class safeiter:
    """
    Takes an iterable and makes it thread-safe for iteration.
    """
    def __init__(self, it):
        self.it = iter(it)
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self.lock:
            return next(self.it)

    def next(self):
        return self.__next__()


def main():
    arg_parser = argparse.ArgumentParser(description="Search for text in a website. Use site's XML sitemap to find URLs."
                                                     "\nReturns CSV compatible output to the standart output.",
                                         formatter_class=argparse.RawTextHelpFormatter)

    arg_parser.add_argument('sitemap',
                            metavar='sitemap_url',
                            type=str,
                            help='XML sitemap URL/path')
    arg_parser.add_argument('search_str',
                            metavar='search_str',
                            type=str,
                            help='Search string')
    arg_parser.add_argument('-v', '--verbose',
                            type=int,
                            required=False,
                            help=VERBOSE_HELP,
                            default=0,
                            choices=LOGGING_LEVELS)
    arg_parser.add_argument('-c', '--concurency',
                            type=int,
                            required=False,
                            default=5,
                            help='How many concurrent connections to make to the server.'
                                 '\n(By default 5)')

    args = arg_parser.parse_args()

    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=LOGGING_LEVELS[args.verbose])

    url = args.sitemap

    results = search_in_site(url, args.search_str, concurency=args.concurency)
    print('\n'.join(map(lambda r: ','.join(map(str, r)), results)))


if __name__ == '__main__':
    main()
