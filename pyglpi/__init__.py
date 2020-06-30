import re
from base64 import b64encode
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from hammock import Hammock


def _resolve_fields(criteria, rev):
    """
    Recursively translates field names to search option numbers

    >>> criteria = [{'field': 'name', 'value': 'name'}]
    >>> search_options = {1: {'uid': 'Computer.name'}}
    >>> _resolve_fields(criteria, _reverse_search_options(search_options))
    [{'field': 1, 'value': 'name'}]

    :param criteria: A list of search criterion objects as defined by the GLPI
                     API, except that the values of "field" keys are field UIDs
                     instead of search option IDs
    :param rev: The result of a call to the searchOptions API endpoint of an
                appropriate itemtype, reversed by a call to
                _reverse_search_options(), that is used to translate the UIDs
                into search option IDs
    :returns: The list of criterion objects with each field UID replaced by its
              search option ID
    """
    if criteria == "":
        return criteria

    try:
        return [
            {
                k: rev[v] if k == 'field' else _resolve_fields(v, rev)
                for k, v in it.items()
            } for it in criteria
        ]
    except (TypeError, AttributeError):
        return criteria


def _reverse_search_options(search_options):
    """
    Reverse the search_options to map a UID to its numeric version

    >>> search_options = {1: {'uid': 'Computer.name'}}
    >>> _reverse_search_options(search_options)
    {'Computer.name': 1, 'name': 1, 1: 1}
    """
    rev = {}
    for k, v in search_options.items():
        try:
            rev[v['uid']] = k
            rev[v['uid'].split('.', 1)[1]] = k
            rev[k] = k
        except (KeyError, TypeError):
            pass

    return rev


def build_qs(d, prefix=None):
    """
    Translate nested dict of query string parameters into PHP style query
    string items

    >>> list(build_qs({'arr': {'foo': 'bar', 'key': [1, 2]}}))
    [('arr[foo]', 'bar'), ('arr[key][0]', 1), ('arr[key][1]', 2)]
    """
    if isinstance(d, str):
        yield (prefix, d)
    elif hasattr(d, 'items'):
        for k, v in d.items():
            yield from build_qs(v, k if prefix is None else f'{prefix}[{k}]')
    else:
        try:
            for i, v in enumerate(d):
                yield from build_qs(v, f'{prefix}[{i}]')
        except TypeError:
            yield (prefix, d)


def search(glpi, itemtype, criteria, search_options=None, **kwargs):
    """
    Wrapper around the GLPI search API

    :param glpi: Instance of `GLPI`
    :param itemtype: Type of GLPI item to use for search (and fetching
                     `search_options` if not given)
    :param criteria: List of GLPI search criterion objects according to API,
                     where fields can be given by search option ID or field UID
                     as given in `search_options`
    :param search_options: Pre-fetched list of search options (useful for
                           caching or if itemtype=AllAssets)
    :param **kwargs: All other keyword options are passed to the search API
                     endpoint
    :returns: Generator of all search results with keys translated back
              according to `search_options`
    """
    if not search_options:
        search_options = glpi.listSearchOptions(itemtype).GET().json()
    rev_search_options = _reverse_search_options(search_options)
    criteria = _resolve_fields(criteria, rev_search_options)
    params = dict(build_qs(criteria, 'criteria'))
    params.update(kwargs)
    if 'forcedisplay' in params:
        params.update(build_qs([
            rev_search_options[x] for x in params['forcedisplay']
        ], 'forcedisplay'))
        del params['forcedisplay']

    result = glpi.search(itemtype).GET(params=params)
    result.raise_for_status()
    prefix_re = re.compile(r'^[^\.]+\.')
    for r in result.ranges:
        for it in r.json()['data']:
            yield {
                prefix_re.sub('', search_options.get(k, {}).get('uid', k)): v
                for k, v in it.items()
            }


class GLPI(Hammock):
    """
    Thin GLPI wrapper around ``hammock.Hammock``.

    Basic usage:

    >>> glpi = GLPI(
    ...     "https://example.org/glpi/apirest.php",
    ...     app_token,
    ...     "user_token ...",
    ... )  # doctest:+SKIP
    >>> computers = []
    >>> for r in glpi.Computer.GET().ranges:
    ...     computers.extend(r.json())  # doctest:+SKIP
    """

    _range_length = None

    def __init__(self, url, app_token, user_token=None, credentials=None):
        super().__init__(url, headers={
            'App-Token': app_token,
            'Content-Type': 'application/json',
        })

        if credentials:
            self._login('Basic %s' % b64encode(':'.join(credentials)))
        elif user_token:
            self._login('user_token %s' % user_token)

    def _login(self, auth):
        response = self.initSession.GET(headers={'Authorization': auth})

        try:
            data = response.json()
            token = data['session_token']
        except ValueError:
            # decoding JSON failed
            pass
        except KeyError:
            # no session_token in response
            pass
        else:
            self._session.headers['Session-Token'] = token

    def _request(self, *args, **kwargs):
        response = super()._request(*args, **kwargs)
        response.raise_for_status()
        return response

    def _rangeiter(self, response):
        yield response

        if response.status_code != 206:
            return

        if 'range' in parse_qs(urlparse(response.request.url).query):
            return

        while True:
            currange = re.match(
                r'^(?P<start>\d+)-(?P<end>\d+)/(?P<total>\d+)$',
                response.headers['Content-Range']
            )
            start, end, total = (
                int(currange.group(x)) for x in ('start', 'end', 'total')
            )

            if end == total - 1:
                break

            length = self._range_length or end - start + 1
            # A bug in GLPI causes a non-ranged query to contain one item less
            # than a ranged query, while returning the same Content-Range
            # header. So when this is the first and thus non-ranged (see the
            # "if 'range' ..." above) query, we have to start the second query
            # one item earlier than usual
            start = end + 1 if start > 0 else end
            end += length

            url = urlparse(response.request.url)
            args = parse_qs(url.query, keep_blank_values=True)
            args['range'] = '{}-{}'.format(start, min(end, total))
            response.request.url = urlunparse(url._replace(query=urlencode(args, True)))
            response = self._session.send(response.request)
            yield response

    def GET(self, *args, **kwargs):
        response = super().GET(*args, **kwargs)
        response.ranges = self._rangeiter(response)
        return response
