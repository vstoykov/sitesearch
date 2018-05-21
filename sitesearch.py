#!/usr/bin/env python3
import argparse
import logging
import sys
import threading
import queue
import urllib.parse

import requests
try:
    # Try fast ans secure ETree first
    from lxml import etree
except ImportError:
    # Fallback to Python's builtin ETree
    from xml.etree import ElementTree as etree


SITEMAP_NAMESPACE = 'http://www.sitemaps.org/schemas/sitemap/0.9'
XMLNS = {'ns': SITEMAP_NAMESPACE}
SITEMAP_INDEX_TAG = '{%s}sitemapindex' % SITEMAP_NAMESPACE
URL_SET_TAG = '{%s}urlset' % SITEMAP_NAMESPACE

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
        # ETree cant't fetch the URL. Fallback with requests
        response = requests.get(url)
        root = etree.fromstring(response.content)
    else:
        root = tree.getroot()

    if root.tag == SITEMAP_INDEX_TAG:
        logger.debug('Processing sitemap index: %s', url)
        for loc in root.iterfind('ns:sitemap/ns:loc', namespaces=XMLNS):
            loc = loc.text.strip()
            logger.debug('Sitemap URL: %s', loc)
            yield from iter_sitemap_urls(loc)
    elif root.tag == URL_SET_TAG:
        logger.debug('Processing sitemap: %s', url)
        for url in root.iterfind('ns:url/ns:loc', namespaces=XMLNS):
            url = url.text.strip()
            logger.debug('Location: %s', url)
            yield url
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
    items = safeiter(iter_sitemap_urls(sitemap_url))

    def worker():
        for item in iter_search_in_urls(items, search_string):
            q.put(item)

    try:
        _thread_executor(target=worker, concurency=concurency)
    finally:
        # Allways close the items generator even if exception is raised.
        # This will ensure that there will be no more itms for threads
        # to process and the program will close almost immediately.
        # If we do not close the generator on exception the threads will
        # continue to run until they finish theirs job.
        items.close()

    sentinel = object()
    q.put(sentinel)

    return iter(q.get, sentinel)


def _thread_executor(target, concurency):
    """
    Simple function to execute given targed concurently with threads
    """
    if concurency == 1:
        # If concurency is 1 there is no need to spawn threads
        target()
        return

    threads = []
    for i in range(concurency):
        thread = threading.Thread(target=target)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


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

    def close(self):
        self.it.close()


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
    unquote = urllib.parse.unquote
    for (url, count) in results:
        print(unquote(url), count, sep=',')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # When Ctrl + C is pressed we want to exit without exception
        sys.exit()
