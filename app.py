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
    for p in doc.xpath('//p'):
        p.tail = '\n\n' + (p.tail or '')
    for br in doc.xpath('//br'):
        br.text = '\n'

    return doc.text_content().strip()


def parse_delete_at(status):
    pattern_absolute = re.compile(
        rf'^#{DELETE_TAG} '
        r'(?:(?:(?P<ayear>\d+)-)?(?P<amonth>\d+)-(?P<adate>\d+))?'
        r'(?:(?:\b| )(?P<ahour>\d+):(?P<aminute>\d+)(?::(?P<asecond>\d+))?)?$',
        re.M)
    pattern_relative = re.compile(
        rf'^#{DELETE_TAG} '
        r'(?:(?P<ryear>\d+)y)?(?:(?P<rmonth>\d+)m)?(?:(?P<rdate>\d+)d)?'
        r'(?: ?)(?:(?P<rhour>\d+)h)?(?:(?P<rminute>\d+)m)?(?:(?P<rsecond>\d+)s)?$',
        re.M)

    content = get_plain_content(status)
    created_at = status.created_at

    if matched := pattern_absolute.search(content):
        delete_at = datetime.datetime(
            int(matched.group('ayear') or created_at.year),
            int(matched.group('amonth') or created_at.month),
            int(matched.group('adate') or created_at.day),
            int(matched.group('ahour') or created_at.hour),
            int(matched.group('aminute') or created_at.minute),
            int(matched.group('asecond') or 0),
        ).replace(tzinfo=created_at.tzinfo)
        if delete_at < status.created_at:
            if not matched.group('adate'):
                delete_at = delete_at.replace(day=created_at.day + 1)
            else:
                delete_at = delete_at.replace(year=delete_at.year + 1)
    elif (matched := pattern_relative.search(content)) and matched.lastgroup is not None:
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
    utcnow = datetime.datetime.now().astimezone(pytz.utc)
    statuses = api.account_statuses(me.id, tagged=DELETE_TAG, limit=100)
    while statuses:
        for status in statuses:
            delete_at = parse_delete_at(status)

            if utcnow >= delete_at:
                print(f'Delete: {status.id} {delete_at}')
                try:
                    api.status_delete(api.status(status.in_reply_to_id))
                except MastodonNotFoundError:
                    pass
                api.status_delete(status)
            else:
                print(f'Skip: {status.id} for {delete_at}')

        statuses = api.fetch_next(statuses)


while True:
    cleanup()
    time.sleep(1 * 60)
