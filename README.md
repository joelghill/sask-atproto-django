# sask-atproto-django
Django implementation of a AT Protocol custom feed.

## Commands

### start_feed
`python3 manage.py start_feed <service uri> --algorithm=<algoritm name>`

where

* **service uri** is the firehose provider. Example: wss://bsky.social
* **alorithm** is either `logger` or `flatlanders`