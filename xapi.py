"""Official X API source for @KoinosNetwork posts: push stream + poll.

Replaces the Nitter/xcancel RSS path as the primary source. Two
independent channels feed the same announcer:

  1. X Activity API — a persistent HTTP stream (`GET /2/activity/stream`)
     carrying `post.create` events for the subscribed account. This is
     the fast path: events arrive within seconds of the post.
  2. A reconciliation poll of `GET /2/users/:id/tweets` with `since_id`.
     The stream is not a guaranteed-delivery channel (X's own developer
     forum has documented silent gaps on the webhook transport), so a
     cheap sweep catches anything the stream missed — a request that
     returns no posts is not billed, and a post already delivered by the
     stream is deduplicated before it can be posted twice.

Only outbound HTTPS is used, so this works unchanged inside the
hardened container (no inbound port, unlike a webhook).

Everything arriving here is treated as untrusted input even though it
comes from X: the event is only relayed when its own author_id matches
the account we subscribed to, and the text goes through the same
escaping/defanging as the RSS path before it reaches Telegram.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

API_BASE = 'https://api.x.com'
STREAM_URL = f'{API_BASE}/2/activity/stream'

# A single event is a few KB. A line beyond this means the framing is
# broken (or the peer is hostile), which is a reason to reconnect
# rather than to keep buffering.
MAX_EVENT_BYTES = 1_000_000
MAX_POLL_BYTES = 4_000_000
# Keepalive newlines were observed roughly every 20 s. Three missed
# keepalives is a dead connection.
STREAM_READ_TIMEOUT = 90
POLL_TIMEOUT = 20
# Never announce more than this per reconciliation sweep, so a long
# outage cannot dump a backlog into the group in one burst.
MAX_POSTS_PER_SWEEP = 3
# Page budget for catching up after downtime. 20 pages x 100 posts is
# over a year of this account's output, so exhausting it means the state
# file is hopelessly stale rather than that the account was busy.
MAX_POLL_PAGES = 20

_RECONNECT_MIN = 2
_RECONNECT_MAX = 300
# A connection must survive this long before it counts as healthy and
# earns a backoff reset.
_STABLE_AFTER = 60
# Consecutive failed sweeps before the API is declared unusable and the
# caller is told to fall back to the mirror.
STALLED_AFTER = 10


def bearer():
    return os.environ.get('X_BEARER_TOKEN', '').strip()


def user_id():
    return os.environ.get('X_USER_ID', '').strip()


def enabled():
    """True when the official API is configured for both channels."""
    return bool(bearer() and user_id().isdigit())


def _auth_headers():
    # The token travels in the header only — never in a URL, so it
    # cannot leak through a log line, a redirect or an error message
    # that echoes the request target. Redirects are refused on every
    # request for the same reason: a 3xx to another host would
    # otherwise replay this header there.
    return {'Authorization': f'Bearer {bearer()}',
            'User-Agent': 'koinbot (+https://github.com/interfecto/koinbot)'}


def _redact(text):
    """Never let the credential reach a log line.

    Upstream error bodies are quoted in log messages; this is the last
    stop in case anything on the far side ever echoes the request
    headers back at us.
    """
    token = bearer()
    if token and token in text:
        text = text.replace(token, '<redacted>')
    return text


async def _read_body(resp, cap):
    """Read a whole response body, refusing one that is too large.

    `StreamReader.read(n)` returns what has arrived so far, not the
    full body, so a response split across TCP segments would otherwise
    be parsed as truncated JSON.
    """
    chunks, total = [], 0
    async for chunk in resp.content.iter_chunked(65536):
        total += len(chunk)
        if total > cap:
            raise RuntimeError(f'response larger than {cap} bytes')
        chunks.append(chunk)
    return b''.join(chunks)


def _clean_text(post):
    """The post body, preferring the untruncated long-form text.

    v2 truncates posts over 280 characters in `text` and carries the
    full body in `note_tweet`. Length is capped later, in the formatter.
    """
    note = post.get('note_tweet')
    if isinstance(note, dict):
        text = note.get('text')
        if isinstance(text, str) and text.strip():
            return text
    text = post.get('text')
    return text if isinstance(text, str) else ''


def _format_date(created):
    """ISO 8601 from the API rendered like the RSS path's pubDate.

    Keeps the relayed message identical in shape whichever source
    produced it. An unparsable timestamp simply drops the line.
    """
    if not isinstance(created, str):
        return ''
    try:
        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
    except ValueError:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')


def _is_original(post):
    """Originals and quote posts yes, replies and reposts no.

    Mirrors the RSS path's rule (it dropped Nitter's "R to"/"RT by"
    prefixes) so switching sources does not change what the group sees.
    """
    refs = post.get('referenced_tweets')
    if isinstance(refs, list):
        for ref in refs:
            if isinstance(ref, dict) and ref.get('type') in ('retweeted', 'replied_to'):
                return False
    # Either marker alone is enough to call it a reply: a stream event
    # may carry in_reply_to_tweet_id without a referenced_tweets entry.
    if post.get('in_reply_to_user_id') or post.get('in_reply_to_tweet_id'):
        return False
    return True


def normalize(post, expect_author):
    """Validate one API post object and reduce it to the relay's shape.

    Returns None for anything that must not be relayed. The author check
    is the important one: it is what stops a post that is not from the
    subscribed account from ever being published under that account's
    name, whatever the envelope claims.
    """
    if not isinstance(post, dict):
        return None
    post_id = post.get('id')
    if not isinstance(post_id, str) or not post_id.isdigit():
        return None
    author = post.get('author_id')
    if not isinstance(author, str):
        # Not a hostile case but a fatal one: without an author the post
        # cannot be attributed, so it is dropped. Logged because it
        # would otherwise look like a silent relay outage.
        logger.warning('post %s has no author_id; not relayed', post_id)
        return None
    if author != expect_author:
        return None
    if not _is_original(post):
        return None
    text = _clean_text(post).strip()
    return {
        'id': int(post_id),
        'text': text or '📷 (media post)',
        'date': _format_date(post.get('created_at')),
    }


async def fetch_timeline(session, since_id=None, max_results=100, pagination_token=None):
    """One page of the account's original posts, newest first.

    Raises on any non-200 so the caller can log and retry later; a
    response that returns no posts costs nothing under pay-per-usage.
    """
    params = {
        'max_results': str(max_results),
        'exclude': 'retweets,replies',
        # author_id is NOT returned by default and the relay refuses any
        # post whose author it cannot confirm, so it must be requested
        # explicitly — without it nothing would ever be published.
        'tweet.fields': 'author_id,created_at,referenced_tweets,note_tweet',
    }
    if since_id:
        params['since_id'] = str(since_id)
    if pagination_token:
        params['pagination_token'] = pagination_token
    url = f'{API_BASE}/2/users/{user_id()}/tweets'
    timeout = aiohttp.ClientTimeout(total=POLL_TIMEOUT)
    async with session.get(url, params=params, headers=_auth_headers(),
                           timeout=timeout, allow_redirects=False) as resp:
        if resp.status != 200:
            body = (await resp.content.read(400)).decode('utf-8', 'replace')
            raise RuntimeError(f'timeline HTTP {resp.status}: {_redact(body[:200])}')
        raw = await _read_body(resp, MAX_POLL_BYTES)
    payload = json.loads(raw.decode('utf-8', 'replace'))
    posts = payload.get('data')
    posts = posts if isinstance(posts, list) else []
    meta = payload.get('meta')
    token = meta.get('next_token') if isinstance(meta, dict) else None
    return posts, (token if isinstance(token, str) else None)


async def fetch_new_posts(session, since_id):
    """Every original post newer than since_id, oldest first.

    Returns (posts, complete). `complete` is False when the backlog was
    larger than the page budget. That distinction matters: pages come
    back newest-first, so a truncated walk is missing the OLDEST posts —
    exactly the ones the caller would announce next. Advancing the floor
    on an incomplete range would step over them for good, so the caller
    is told rather than silently handed a partial answer.
    """
    collected, token, expect = [], None, user_id()
    complete = False
    for _ in range(MAX_POLL_PAGES):
        page, token = await fetch_timeline(session, since_id=since_id,
                                           pagination_token=token)
        for raw_post in page:
            post = normalize(raw_post, expect)
            if post:
                collected.append(post)
        if not token or not page:
            complete = True
            break
    collected.sort(key=lambda p: p['id'])
    return collected, complete


async def latest_post(session):
    """Newest original post, for the /x command. None when unavailable."""
    page, _ = await fetch_timeline(session, max_results=5)
    expect = user_id()
    posts = [p for p in (normalize(raw, expect) for raw in page) if p]
    posts.sort(key=lambda p: p['id'], reverse=True)
    return posts[0] if posts else None


def _event_post(event, expect_author):
    """The relayable post inside one stream event, or None.

    An event is only acted on when it is a post creation for the very
    account this bot subscribed to — checked on the subscription filter
    AND on the post's own author. Anything else (a different event type,
    another account, a malformed frame) is ignored rather than guessed
    at.
    """
    if not isinstance(event, dict):
        return None
    # Frames arrive wrapped in an outer "data" object. Unwrap it before
    # looking for the envelope fields, but accept the bare shape too:
    # reading the wrong level here fails silently, relaying nothing
    # while the connection still looks healthy.
    if 'event_type' not in event and isinstance(event.get('data'), dict):
        event = event['data']
    if event.get('event_type') != 'post.create':
        return None
    filt = event.get('filter')
    if isinstance(filt, dict):
        filtered_user = filt.get('user_id')
        if isinstance(filtered_user, str) and filtered_user != expect_author:
            return None
    payload = event.get('payload')
    if not isinstance(payload, dict):
        return None
    # Some deliveries nest the Post one level deeper; accept both.
    post = payload.get('data') if isinstance(payload.get('data'), dict) else payload
    return normalize(post, expect_author)


async def ensure_subscription(session):
    """Subscribe to the account's post.create events if not already.

    The stream only carries events for subscriptions this app holds, and
    a subscription outlives any single deployment — so setting the token
    and the user id alone is not enough, and creating one blindly on
    every start would pile up duplicates. Checked first, created only if
    missing. A failure here is logged, not fatal: the reconciliation
    sweep still delivers posts, just more slowly.
    """
    target = user_id()
    timeout = aiohttp.ClientTimeout(total=POLL_TIMEOUT)
    url = f'{API_BASE}/2/activity/subscriptions'
    async with session.get(url, headers=_auth_headers(), timeout=timeout,
                           allow_redirects=False) as resp:
        if resp.status != 200:
            body = (await resp.content.read(300)).decode('utf-8', 'replace')
            raise RuntimeError(f'subscription list HTTP {resp.status}: '
                               f'{_redact(body[:200])}')
        raw = await _read_body(resp, MAX_POLL_BYTES)
    existing = json.loads(raw.decode('utf-8', 'replace')).get('data')
    for sub in existing if isinstance(existing, list) else []:
        if not isinstance(sub, dict):
            continue
        filt = sub.get('filter')
        if sub.get('event_type') == 'post.create' and isinstance(filt, dict) \
                and filt.get('user_id') == target:
            logger.info('X activity subscription present (%s)',
                        sub.get('subscription_id'))
            return sub.get('subscription_id')
    body = {'event_type': 'post.create', 'filter': {'user_id': target},
            'tag': 'koinbot'}
    async with session.post(url, headers=_auth_headers(), json=body,
                            timeout=timeout, allow_redirects=False) as resp:
        if resp.status not in (200, 201):
            detail = (await resp.content.read(300)).decode('utf-8', 'replace')
            raise RuntimeError(f'subscription create HTTP {resp.status}: '
                               f'{_redact(detail[:200])}')
        raw = await _read_body(resp, MAX_POLL_BYTES)
    created = json.loads(raw.decode('utf-8', 'replace'))
    sub_id = created.get('data', {}).get('subscription', {}).get('subscription_id')
    logger.info('X activity subscription created (%s)', sub_id)
    return sub_id


def _parse_frame(line, expect_author):
    """One stream line to a relayable post, or None.

    Keepalives are empty lines. Anything else that does not turn into a
    post is logged by shape only — never by content — so that a change
    in X's envelope shows up as a diagnosable log line instead of a
    stream that looks connected but relays nothing.
    """
    if not line:
        return None  # keepalive
    if len(line) > MAX_EVENT_BYTES:
        logger.warning('oversized stream frame (%d bytes), skipped', len(line))
        return None
    try:
        event = json.loads(line.decode('utf-8', 'replace'))
    except ValueError:
        logger.warning('unparsable stream frame, skipped')
        return None
    post = _event_post(event, expect_author)
    if post is None and isinstance(event, dict):
        inner = event.get('data') if isinstance(event.get('data'), dict) else event
        logger.info('stream frame not relayed (event_type=%r, keys=%s)',
                    inner.get('event_type') if isinstance(inner, dict) else None,
                    sorted(inner)[:8] if isinstance(inner, dict) else None)
    return post


async def stream_loop(on_post, session=None):
    """Read the Activity stream forever, calling on_post for each post.

    Reconnects with exponential backoff. The loop never raises: a
    permanently broken stream degrades to the reconciliation poll, it
    does not take the bot down.
    """
    expect = user_id()
    backoff = _RECONNECT_MIN
    owns_session = session is None
    session = session or aiohttp.ClientSession()
    logger.info('X activity stream starting (user %s)', expect)
    subscribed = False
    try:
        while True:
            connected_at = None
            try:
                if not subscribed:
                    await ensure_subscription(session)
                    subscribed = True
                # No total timeout: this connection is meant to stay
                # open. sock_read alone detects a peer that stopped
                # sending keepalives (observed every 20s).
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=20,
                                                sock_read=STREAM_READ_TIMEOUT)
                async with session.get(STREAM_URL, headers=_auth_headers(),
                                       timeout=timeout,
                                       allow_redirects=False) as resp:
                    if resp.status != 200:
                        body = (await resp.content.read(300)).decode('utf-8', 'replace')
                        raise RuntimeError(f'stream HTTP {resp.status}: '
                                           f'{_redact(body[:200])}')
                    logger.info('X activity stream connected')
                    connected_at = time.monotonic()
                    buf = b''
                    async for chunk in resp.content.iter_chunked(65536):
                        buf += chunk
                        while b'\n' in buf:
                            line, buf = buf.split(b'\n', 1)
                            post = _parse_frame(line.strip(), expect)
                            if post:
                                await on_post(post)
                        # Bound the partial line too: without a newline
                        # this buffer would otherwise grow unchecked.
                        if len(buf) > MAX_EVENT_BYTES:
                            raise RuntimeError('oversized stream frame')
                    raise RuntimeError('stream closed by peer')
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Only a connection that actually held up counts as
                # success. Resetting on the 200 alone turns a peer that
                # accepts and immediately drops us into a hot loop at
                # the minimum delay, forever.
                if connected_at and time.monotonic() - connected_at >= _STABLE_AFTER:
                    backoff = _RECONNECT_MIN
                logger.warning('X activity stream lost (%s); reconnecting in %ss',
                               _redact(str(e)), backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_MAX)
    finally:
        if owns_session:
            await session.close()


async def poll_loop(announcer, poll_seconds, session=None, on_stalled=None):
    """Sweep the timeline for anything the stream did not deliver.

    The announcer is shared with the stream, so a post that arrived on
    both paths is published once. Unlike the stream, this sweep sees a
    whole id range at a time, which is why it — and only it — advances
    the floor that becomes the next since_id.
    """
    owns_session = session is None
    session = session or aiohttp.ClientSession()
    logger.info('X timeline reconciliation every %ss', poll_seconds)
    failures = 0
    stalled_reported = False
    first = True
    try:
        while True:
            # The very first pass runs immediately. On a fresh install
            # the floor is set from this pass, and anything posted
            # before it lands is adopted silently — so that window must
            # be milliseconds, not a full poll interval.
            if not first:
                await asyncio.sleep(poll_seconds)
            first = False
            try:
                if announcer.floor is None:
                    # No baseline yet: adopt the current head without
                    # announcing, so a fresh deployment never replays
                    # history into the group.
                    post = await latest_post(session)
                    if post:
                        announcer.set_baseline(post['id'])
                    failures = 0
                    continue
                posts, complete = await fetch_new_posts(session, announcer.floor)
                if not complete:
                    # The backlog is older than the page budget, so the
                    # posts we would announce first are out of reach.
                    # Re-baseline to the head instead: months-old news
                    # does not belong in the group, and a silent floor
                    # advance would hide the skip.
                    newest = posts[-1]['id'] if posts else None
                    logger.error(
                        'X backlog beyond %d pages; skipping to %s without '
                        'announcing (state was too far behind)',
                        MAX_POLL_PAGES, newest)
                    if newest:
                        announcer.advance_floor(newest)
                    continue
                sent = 0
                for post in posts:
                    if announcer.seen(post['id']):
                        announcer.advance_floor(post['id'])
                        continue
                    if sent >= MAX_POSTS_PER_SWEEP:
                        break
                    if not await announcer.announce(post):
                        break  # send failed; retry this post next sweep
                    announcer.advance_floor(post['id'])
                    sent += 1
                failures = 0
                stalled_reported = False
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failures += 1
                logger.error('X timeline reconciliation failed (%d in a row): %s',
                             failures, _redact(str(e)))
                # An expired token, exhausted credits or a revoked app
                # would otherwise leave both API paths retrying in
                # silence while the group hears nothing at all. Hand
                # back to the caller once, so it can fall back.
                if on_stalled and not stalled_reported and failures >= STALLED_AFTER:
                    stalled_reported = True
                    try:
                        await on_stalled(failures)
                    except Exception as cb_error:
                        logger.error('stall handler failed: %s', cb_error)
    finally:
        if owns_session:
            await session.close()
