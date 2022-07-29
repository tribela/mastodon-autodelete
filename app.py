import datetime
import os
import re
import time

from dateutil.relativedelta import relativedelta

import pytz
from mastodon import Mastodon, MastodonNotFoundError
from lxml import html

ACCESS_TOKEN = os.getenv('MASTODON_ACCESS_TOKEN')
MASTODON_HOST = os.getenv('MASTODON_HOST')
DELETE_TAG = 'deleteit'

api = Mastodon(api_base_url=MASTODON_HOST, access_token=ACCESS_TOKEN)
me = api.account_verify_credentials()


def get_plain_content(status):
    doc = html.fromstring(status.content)
    for link in doc.xpath('//a'):
        link.drop_tree()
    for p in doc.xpath('//p'):
        p.tail = '\n\n' + (p.tail or '')
    for br in doc.xpath('//br'):
        br.content = '\n'

    return doc.text_content().strip()


def parse_delete_at(status):
    pattern_absolute = re.compile(r'^(?:(?P<ayear>\d+)-)?(?P<amonth>\d+)-(?P<adate>\d+)(?: (?P<ahour>\d+):(?P<aminute>\d+)(?::(?P<asecond>\d+))?)?$')
    pattern_relative = re.compile(r'^(?:(?P<ryear>\d+)y)?(?:(?P<rmonth>\d+)m)?(?:(?P<rdate>\d+)d)?(?: ?)(?:(?P<rhour>\d+)h)?(?:(?P<rminute>\d+)m)?(?:(?P<rsecond>\d+)s)?$')

    content = get_plain_content(status)
    created_at = status.created_at

    if matched := pattern_absolute.match(content):
        delete_at = datetime.datetime(
            int(matched.group('ayear') or status.created_at.year),
            int(matched.group('amonth')),
            int(matched.group('adate')),
            int(matched.group('ahour') or created_at.hour),
            int(matched.group('aminute') or created_at.minute),
            int(matched.group('asecond') or 0),
        ).astimezone(created_at.tzinfo)
        if delete_at < status.created_at:
            delete_at = delete_at.replace(year=delete_at.year + 1)
    elif (matched := pattern_relative.match(content)) and matched.lastgroup is not None:
        delta = relativedelta(
            year=int(matched.group('ryear') or 0),
            months=int(matched.group('rmonth') or 0),
            days=int(matched.group('rdate') or 0),
            hours=int(matched.group('rhour') or 0),
            minutes=int(matched.group('rminute') or 0),
            seconds=int(matched.group('rsecond') or 0),
        )
        delete_at = status.created_at + delta
    else:
        delete_at = status.created_at + relativedelta(days=1)

    return delete_at


def cleanup():
    utcnow = datetime.datetime.utcnow().astimezone(pytz.utc)
    statuses = api.account_statuses(me.id, tagged=DELETE_TAG, limit=100)
    while statuses:
        for status in statuses:
            delete_at = parse_delete_at(status)

            if utcnow >= delete_at:
                print(f'Delete: {status.id} {get_plain_content(status)}')
                try:
                    api.status_delete(api.status(status.in_reply_to_id))
                except MastodonNotFoundError:
                    pass
                api.status_delete(status)
            else:
                print(f'Skip: {status.id} {get_plain_content(status)}')

        statuses = api.fetch_next(statuses)


while True:
    cleanup()
    time.sleep(5 * 60)
