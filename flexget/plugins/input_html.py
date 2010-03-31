import urlparse
import logging
import BeautifulSoup
import urllib
import zlib
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.soup import get_soup
from flexget.plugins.cached_input import cached
from flexget.utils.tools import urlopener

log = logging.getLogger('html')


class InputHtml:
    """
        Parses urls from html page. Usefull on sites which have direct download
        links of any type (mp3, jpg, torrent, ...).

        Many anime-fansubbers do not provide RSS-feed, this works well in many cases.

        Configuration expects url parameter.

        Note: This returns ALL links on url so you need to configure filters
        to match only to desired content.
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        advanced = root.accept('dict')
        advanced.accept('url', key='url', required=True)
        advanced.accept('text', key='dump')
        advanced.accept('text', key='title_from')
        regexps = advanced.accept('list', key='links_re')
        regexps.accept('regexp')
        return root

    @cached('html', 'url')
    @internet(log)
    def on_feed_input(self, feed):
        config = feed.config['html']
        if not isinstance(config, dict):
            config = {}
        pageurl = feed.get_input_url('html')

        log.debug('InputPlugin html requesting url %s' % pageurl)

        page = urlopener(pageurl, log)
        soup = get_soup(page)
        log.debug('Detected encoding %s' % soup.originalEncoding)

        # dump received content into a file
        if 'dump' in config:
            name = config['dump']
            log.info('Dumping %s into %s' % (pageurl, name))
            data = soup.prettify()
            f = open(name, 'w')
            f.write(data)
            f.close()

        self.create_entries(feed, pageurl, soup, config)

    def create_entries(self, feed, pageurl, soup, config):

        queue = []
        duplicates = {}
        duplicate_limit = 4

        def title_exists(title):
            """Helper method. Return True if title is already added to entries"""
            for entry in queue:
                if entry['title'] == title:
                    return True

        for link in soup.findAll('a'):
            # not a valid link
            if not link.has_key('href'):
                continue
            # no content in the link
            if not link.contents:
                continue

            url = link['href']

            # get only links matching regexp
            regexps = config.get('links_re', None)
            if regexps:
                import re
                accept = False
                for regexp in regexps:
                    if re.search(regexp, url):
                        accept = True
                if not accept:
                    continue

            title = link.contents[0]

            # tag inside link
            if isinstance(title, BeautifulSoup.Tag):
                log.log(5, 'title is tag: %s' % title)
                continue

            # just unable to get any decent title
            if title is None:
                title = link.next.string
                if title is None:
                    continue

            # strip unicode white spaces
            title = title.replace(u'\u200B', u'').strip()

            if not title:
                continue

            # fix broken urls
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)

            title_from = config.get('title_from', 'auto')
            if title_from == 'url':
                parts = urllib.splitquery(url[url.rfind('/')+1:])
                title = urllib.unquote_plus(parts[0])
                log.debug('title from url: %s' % title)
            elif title_from == 'title':
                if not link.has_key('title'):
                    log.warning('Link %s doesn\t have title attribute, ignored.')
                    continue
                title = link['title']
                log.debug('title from title: %s' % title)
            elif title_from == 'auto':
                # automatic mode, check if title is unique
                # if there are too many duplicate titles, switch to title_from: url
                if title_exists(title):
                    # ignore index links as a counter
                    if 'index' in title and len(title) < 10:
                        continue
                    duplicates.setdefault(title, 0)
                    duplicates[title] += 1
                    if duplicates[title] > duplicate_limit:
                        log.info('Link names seem to be useless, auto-enabling \'title_from: url\'. This may not work well, you might need to configure it.')
                        config['title_from'] = 'url'
                        # start from the beginning  ...
                        self.create_entries(feed, pageurl, soup, config)
                        return
            elif title_from == 'link' or title_from == 'contents':
                # link from link name
                log.debug('title from link: %s' % title)
                pass
            else:
                raise PluginError('Unknown title_from value %s' % title_from)

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get up to first .torrent)
            # TODO: hack
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find('.torrent')]
                
            if title_exists(title):
                # title link should be unique, add CRC32 to end if it's not
                hash = zlib.crc32(url)
                crc32 = '%08X' % (hash & 0xFFFFFFFF)
                title = '%s [%s]' % (title, crc32)
                # truly duplicate, title + url crc already exists in queue
                if title_exists(title):
                    continue
                log.debug('uniqued title to %s' % title)

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            queue.append(entry)

        # add from queue to feed
        feed.entries.extend(queue)


register_plugin(InputHtml, 'html')
