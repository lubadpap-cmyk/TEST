import urllib.request
import urllib.error
import ssl
import re
import time
import random

# Create an unverified SSL context to ensure we don't fail on SSL validation issues
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# List of common User-Agents to rotate and avoid blocking
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }


def is_valid_username_format(username):
    """Validate Telegram username format before checking availability."""
    return bool(re.match(r'^[a-z][a-z0-9_]{4,31}$', username))


def check_telegram(username):
    """
    Checks Telegram availability in a conservative, resilient way.
    Returns:
        True if the username looks available.
        False if clearly taken.
        None if the request failed or the site is rate-limiting us.
    """
    url = f"https://t.me/{username}"
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as response:
            if response.status != 200:
                print(f"Telegram returned status {response.status} for {username}")
                return None

            html = response.read().decode('utf-8', errors='ignore').lower()
            if any(marker in html for marker in ["tgme_page_title", "this page could not be found", "page not found", "username is already taken", "is unavailable"]):
                return False

            if any(marker in html for marker in ["create a username", "choose a username", "available", "not found"]):
                return True

            return True

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} checking Telegram for {username}")
        if e.code == 429:
            return None
        if e.code in (404, 410):
            return True
        return None
    except Exception as e:
        print(f"Network error checking Telegram for {username}: {e}")
        return None

def check_fragment(username):
    """
    Checks Fragment availability without relying on fragile table markup.
    Returns True if the username appears free, False if clearly taken/auctioned/sold,
    and None on transport/rate-limit errors.
    """
    url = f"https://fragment.com/?query={username}"
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as response:
            if response.status != 200:
                print(f"Fragment returned status {response.status} for {username}")
                return None

            html = response.read().decode('utf-8', errors='ignore').lower()
            if any(marker in html for marker in ["already claimed", "taken", "on auction", "for sale", "sold", "reserved"]):
                return False

            if any(marker in html for marker in ["available", "unavailable", "search results"]):
                return True

            return True

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} checking Fragment for {username}")
        if e.code == 429:
            return None
        return None
    except Exception as e:
        print(f"Network error checking Fragment for {username}: {e}")
        return None

def is_username_available(username):
    """
    Double checks username availability on both Telegram and Fragment.
    Returns:
        True: Username appears free.
        False: Username is clearly taken.
        None: Error occurred (rate limited, connection timeout).
    """
    username = username.strip().replace("@", "").lower()

    if not is_valid_username_format(username):
        return False

    tg_check = check_telegram(username)
    if tg_check is False:
        return False
    if tg_check is None:
        return None

    time.sleep(0.3)

    frag_check = check_fragment(username)
    if frag_check is False:
        return False
    if frag_check is None:
        return None

    return True
