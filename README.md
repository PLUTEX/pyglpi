# pyglpi

This is thin wrapper around the [GLPI REST API] using [Hammock] and aiding in
session creation, iterating through result ranges and translating search options
between readable and persistent UIDs and the IDs used by the API.

[GLPI REST API]: https://github.com/glpi-project/glpi/blob/9.4/bugfixes/apirest.md
[Hammock]: https://github.com/kadirpekel/hammock

## Usage

### Setup

Register the application you are using the API from in your GLPI instance under
Setup → General → API to receive the `app_token`.

### Login using user token

You can generate the `user_token` in your profile. This is the recommended way
to authenticate to GLPI if you have to store the credentials.

You can then login like this:
```python
glpi = pyglpi.GLPI(
    'https://glpi.example.org/apirest.php',
    app_token,
    user_token='0123456789abcdef0123456789abcdef01234567',
)
```

### Login using username and password

Use this only when the API is used with different, user-provided credentials.

```python
glpi = pyglpi.GLPI(
    'https://glpi.example.org/apirest.php',
    app_token,
    credentials=('username', 'password'),
)
```

### Calling API methods directly / Paged replies

All API endpoints are callable as usual with [Hammock]. However, for GET
requests, the special `ranges` attribute is added to the response to aid in
iterating through paged responses:

```python
for result_range in glpi.Computer.GET().ranges:
    for item in result_range:
        print(item['name'])
```

### Search

There is a special helper function to convert the search criteria from a python
datastructure to the correct GET parameters, on-the-fly translating field names
to the numeric search option IDs that the API expects, and translating the
result keys back to the readable UIDs.

```python
criteria = [{
    'field': 'name',
    'searchtype': 'contains',
    'value': '.example.net$',
}]

for item in pyglpi.search(glpi, 'Computer', criteria):
    print(item['name'])
```

Note that while in the input parameter `criteria` the `search` function accepts
both variants `Computer.name` and just `name`, as well as the plain numeric ID
`1`, the result will always have the itemtype stripped from the full UID as
returned by searchOptions API endpoint, to be at least similar to the fetching
of items (see above).

Also note that ranges are automatically iterated through inside the helper
function.

#### Search for AllAssets

The API supports searching for all kinds of assets in a single query. However,
because AllAssets cannot be passed to the `searchOptions` endpoint, we have to
use the IDs from some other itemtype. This is supported by passing in the
`search_options` to use for translation:

```python
criteria = [{
    'field': 'name',
    'searchtype': 'contains',
    'value': '.example.net$',
}]
search_options = glpi.searchOptions.Computer.GET().json()

for item in pyglpi.search(glpi, 'AllAssets', criteria, search_options):
    print(item['name'])
```
