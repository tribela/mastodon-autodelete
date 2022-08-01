import datetime
import logging
import logging.config
import os
import re
import time

import dateutil.parser
from dateutil.relativedelta import relativedelta

import pytz
from mastodon import Mastodon, MastodonNotFoundError
from lxml import html

ACCESS_TOKEN = os.getenv('MASTODON_ACCESS_TOKEN')
MASTODON_HOST = os.getenv('MASTODON_HOST')
DELETE_TAG = 'deleteit'
LOCAL_TIMEZONE = pytz.timezone('Asia/Seoul')

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('App')

api = Mastodon(api_base_url=MASTODON_HOST, access_token=ACCESS_TOKEN)
me = api.account_verify_credentials()

logger.info(f'I am {me.username}')


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
        r'(?:(?P<ryear>\d+)y)?(?:(?P<rmonth>\d+)m)?(?:(?P<rweek>\d+)w)?(?:(?P<rdate>\d+)d)?'
        r'(?: ?)(?:(?P<rhour>\d+)h)?(?:(?P<rminute>\d+)m)?(?:(?P<rsecond>\d+)s)?$',
        re.M)

    content = get_plain_content(status)
    if status.edited_at:
        last_updated_at = dateutil.parser.parse(status.edited_at)
    else:
        last_updated_at = status.created_at
    last_updated_at = last_updated_at.astimezone(LOCAL_TIMEZONE)

    if matched := pattern_absolute.search(content):
        logger.debug('Using absolute pattern')
        delete_at = datetime.datetime(
            int(matched.group('ayear') or last_updated_at.year),
            int(matched.group('amonth') or last_updated_at.month),
            int(matched.group('adate') or last_updated_at.day),
            int(matched.group('ahour') or last_updated_at.hour),
            int(matched.group('aminute') or last_updated_at.minute),
            int(matched.group('asecond') or 0),
        ).astimezone(LOCAL_TIMEZONE)
        if delete_at < last_updated_at:
            if not matched.group('adate'):  # Only hours
                delete_at = delete_at.replace(day=delete_at.day + 1)
            else:  # Date given
                delete_at = delete_at.replace(year=delete_at.year + 1)

    elif (matched := pattern_relative.search(content)) and matched.lastgroup is not None:
        logger.debug('Using relative pattern')
        delta = relativedelta(
            year=int(matched.group('ryear') or 0),
            months=int(matched.group('rmonth') or 0),
            days=(
                int(matched.group('rweek') or 0) * 7 +
                int(matched.group('rdate') or 0)),
            hours=int(matched.group('rhour') or 0),
            minutes=int(matched.group('rminute') or 0),
            seconds=int(matched.group('rsecond') or 0),
        )
        delete_at = last_updated_at + delta
    else:
        logger.debug('Using default pattern')
        delete_at = last_updated_at + relativedelta(days=1)

    return delete_at


def cleanup():
    utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    statuses = api.account_statuses(me.id, tagged=DELETE_TAG, limit=100)
    while statuses:
        for status in statuses:
            delete_at = parse_delete_at(status)

            if utcnow >= delete_at:
                logger.info(f'Delete: {status.id} {delete_at}')
                try:
                    api.status_delete(api.status(status.in_reply_to_id))
                except MastodonNotFoundError:
                    pass
                api.status_delete(status)
            else:
                logger.debug(f'Skip: {status.id} for {delete_at}')

        logger.debug('Fetch next page')
        statuses = api.fetch_next(statuses)


while True:
    logger.debug('Start cleanup')
    cleanup()
    time.sleep(1 * 60)
