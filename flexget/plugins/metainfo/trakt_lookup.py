from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.manager import Session

try:
    from flexget.plugins.api_trakt import ApiTrakt
    lookup_series = ApiTrakt.lookup_series
except ImportError:
    raise plugin.DependencyError(issued_by='trakt_lookup', missing='api_trakt',
                                 message='trakt_lookup requires the `api_trakt` plugin')


log = logging.getLogger('trakt_lookup')


class PluginTraktLookup(object):
    """Retrieves trakt information for entries. Uses series_name,
    series_season, series_episode from series plugin.

    Example:

    trakt_lookup: yes

    Primarily used for passing trakt information to other plugins.
    Among these is the IMDB url for the series.

    This information is provided (via entry):
    series info:
    trakt_series_name
    trakt_series_runtime
    trakt_series_first_aired_epoch
    trakt_series_first_aired_iso
    trakt_series_air_time
    trakt_series_content_rating
    trakt_series_genres
    trakt_sereis_banner_url
    trakt_sereis_fanart_url
    trakt_series_imdb_url
    trakt_series_trakt_url
    trakt_series_imdb_id
    trakt_series_tvdb_id
    trakt_series_actors
    trakt_series_country
    trakt_series_year
    trakt_series_tvrage_id
    trakt_series_status
    trakt_series_overview

    trakt_ep_name
    trakt_ep_season
    trakt_ep_number
    trakt_ep_overview
    trakt_ep_first_aired_epoch
    trakt_ep_first_aired_iso
    trakt_ep_image_url
    trakt_ep_id
    trakt_ep_tvdb_id

  """

  # Series info
    series_map = {
        'trakt_series_name': 'title',
        'trakt_series_year': 'year',
        'imdb_id': 'imdb_id',
        'tvdb_id': 'tvdb_id',
        'tmdb_id': 'tmdb_id',
        'trakt_show_id': 'id',
        'trakt_series_slug': 'slug',
        'trakt_series_tvrage': 'tvrage_id',
        'trakt_series_runtime': 'runtime',
        'trakt_series_first_aired': 'first_aired',
        'trakt_series_air_time': 'air_time',
        'trakt_series_air_day': 'air_day',
        'trakt_series_content_rating': 'certification',
        'trakt_genres': lambda i: [db_genre.name for db_genre in i.genres],
        'trakt_series_network': 'network',
        'imdb_url': lambda series: series.imdb_id and 'http://www.imdb.com/title/%s' % series.imdb_id,
        'trakt_series_url': lambda series: series.slug and 'http://trakt.tv/shows/%s' % series.slug,
        #'trakt_series_actors': lambda series: [actors.name for actors in series.actors],
        'trakt_series_country': 'country',
        'trakt_series_status': 'status',
        'trakt_series_overview': 'overview',
        'trakt_series_rating': 'rating',
        'trakt_series_aired_episodes': 'aired_episodes',
        'trakt_series_episodes': lambda show: [episodes.title for episodes in show.episodes]
    }

  # Episode info
    episode_map = {
        'trakt_ep_name': 'title',
        'trakt_ep_imdb_id': 'imdb_id',
        'trakt_ep_tvdb_id': 'tvdb_id',
        'trakt_ep_tmdb_id': 'tmdb_id',
        'trakt_ep_tvrage': 'tvrage_id',
        'trakt_episode_id': 'id',
        'trakt_ep_first_aired': 'first_aired',
        'trakt_ep_overview': 'overview',
        'trakt_ep_abs_number': 'number_abs',
        'trakt_season': 'season',
        'trakt_episode': 'number',
        'trakt_ep_id': lambda ep: 'S%02dE%02d' % (ep.season, ep.number),
        }

    # Movie info
    movie_map = {
        'movie_name': 'title',
        'movie_year': 'year',
        'trakt_name': 'title',
        'trakt_year': 'year',
        'trakt_movie_id': 'id',
        'trakt_movie_slug': 'slug',
        'imdb_id': 'imdb_id',
        'tmdb_id': 'tmdb_id',
        'trakt_tagline': 'tagline',
        'trakt_overview': 'overview',
        'trakt_released': 'released',
        'trakt_runtime': 'runtime',
        'trakt_rating': 'rating',
        'trakt_votes': 'votes',
        'trakt_language': 'language',
        'trakt_genres': lambda i: [db_genre.name for db_genre in i.genres]
    }

    schema = {'type': 'boolean'}

    def lazy_series_lookup(self, entry, field):
        """Does the lookup for this entry and populates the entry fields."""
        with Session() as session:
            lookupargs = {'title': entry.get('series_name', eval_lazy=False),
                          #'year': entry.get('year', eval_lazy=False),
                          'trakt_id': entry.get('trakt_show_id', eval_lazy=False),
                          'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                          'tmdb_id': entry.get('tmdb_id', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
            except LookupError as e:
                log.debug(e.message)
                entry.unregister_lazy_fields(self.series_map, self.lazy_series_lookup)
                # Also clear episode fields, since episode lookup cannot succeed without series lookup
                entry.unregister_lazy_fields(self.episode_map, self.lazy_episode_lookup)
            else:
                entry.update_using_map(self.series_map, series)
        return entry[field]

    def lazy_episode_lookup(self, entry, field):
        with Session(expire_on_commit=False) as session:
            lookupargs = {'title': entry.get('series_name', eval_lazy=False),
                          'trakt_id': entry.get('trakt_show_id', eval_lazy=False),
                          'session': session}
            try:
                series = lookup_series(**lookupargs)
                episode = series.get_episode(entry['series_season'], entry['series_episode'])
            except LookupError as e:
                log.debug('Error looking up trakt episode information for %s: %s' % (entry['title'], e.args[0]))
                entry.unregister_lazy_fields(self.episode_map, self.lazy_episode_lookup)
            else:
                entry.update_using_map(self.episode_map, episode)
        return entry[field]

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        for entry in task.entries:

            if entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False):
                entry.register_lazy_fields(self.series_map, self.lazy_series_lookup)

                if 'series_season' in entry and 'series_episode' in entry:
                    entry.register_lazy_fields(self.episode_map, self.lazy_episode_lookup)
            else:
                entry.register_lazy_fields(self.movie_map, self.lazy_movie_lookup)
                    entry.register_lazy_func(self.lazy_episode_lookup, self.episode_map)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTraktLookup, 'trakt_lookup', api_ver=3)
