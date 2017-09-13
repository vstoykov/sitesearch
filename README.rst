# Site Searcher

You can search for given string in a website by providing url to a sitemap and desired string.

## Usage

::

    usage: sitesearch.py [-h] [-v {0,1,2}] [-c CONCURENCY] sitemap_url search_str

    Search for text in a website. Use site's XML sitemap to find URLs.
    Returns CSV compatible output to the standart output.

    positional arguments:
    sitemap_url           XML sitemap URL/path
    search_str            Search string

    optional arguments:
    -h, --help            show this help message and exit
    -v {0,1,2}, --verbose {0,1,2}
                            Verbose mode. Controls the script output
                                0 - print output only in case of errors
                                1 - prints the result count plus list of failed URLs(if any)
                                2 - print all checked URLs
    -c CONCURENCY, --concurency CONCURENCY
                            How many concurrent connections to make to the server.
                            (By default 5)

## Requires

It runs on Python 2 and 3. Requires :code:`requests` and :code:`lxml`
