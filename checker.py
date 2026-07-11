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
    Checks if a username is taken on Telegram.
    Returns:
        True if the username is NOT taken (available on Telegram).
        False if taken (has profile, channel, or bot).
        None if there is an error (e.g. rate limit, HTTP 429).
    """
    url = f"https://t.me/{username}"
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as response:
            if response.status != 200:
                print(f"Telegram returned status {response.status} for {username}")
                return None
            
            html = response.read().decode('utf-8')
            
            # If tgme_page_title is in the HTML, it is occupied by an active entity
            if "tgme_page_title" in html:
                return False # Taken
            
            return True # Not taken on Telegram
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} checking Telegram for {username}")
        if e.code == 429:
            # Rate limit hit
            return None
        # Other HTTP errors might indicate restriction/ban, treat as occupied/error
        return None
    except Exception as e:
        print(f"Network error checking Telegram for {username}: {e}")
        return None

def check_fragment(username):
    """
    Checks if a username is active/reserved/sold on Fragment.com.
    Returns:
        True if the username is NOT active on Fragment (status is 'Unavailable').
        False if taken, on auction, for sale, or sold.
        None if error.
    """
    url = f"https://fragment.com/?query={username}"
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as response:
            if response.status != 200:
                print(f"Fragment returned status {response.status} for {username}")
                return None
                
            html = response.read().decode('utf-8')
            
            # Find the search results table rows
            rows = re.findall(r'<tr[^>]*tm-row-selectable[^>]*>.*?</tr>', html, re.DOTALL)
            
            # Search for the exact username row
            target_at = f"@{username.lower()}"
            for row in rows:
                if target_at in row.lower():
                    # We found the row for our username!
                    # Parse status text
                    # It is typically in: class="...tm-status-..."
                    status_match = re.search(r'class="[^"]*tm-status-([^"]+)"[^>]*>(.*?)<', row)
                    if status_match:
                        status_class = status_match.group(1).lower()
                        status_text = status_match.group(2).strip().lower()
                        
                        # "unavailable" means it is a standard free username (not premium)
                        # and is NOT active on Fragment auctions or as a sold NFT.
                        if status_text == "unavailable" or status_class == "unavail":
                            return True # Free to claim if not taken on Telegram
                            
                        # If status is "On auction", "For sale", "Sold", "Taken"
                        return False # Taken / On Fragment
            
            # If the row wasn't found, it might be available, but we'll be cautious
            # Usually, standard names always show up as "Unavailable" in the table.
            # If the query returned no rows or something else, let's treat it as available on Fragment.
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
        True: Username is free (passes both checks).
        False: Username is taken (fails at least one check).
        None: Error occurred (rate limited, connection timeout).
    """
    # Sanitize input
    username = username.strip().replace("@", "").lower()

    if not is_valid_username_format(username):
        return False
    
    # 1. Telegram check
    tg_check = check_telegram(username)
    if tg_check is False:
        # Taken on Telegram, no need to query Fragment
        return False
    elif tg_check is None:
        # Error (likely rate limit), abort to prevent false positives
        return None
        
    # Introduce a minor delay to avoid hitting rate limits too quickly
    time.sleep(0.3)
    
    # 2. Fragment check
    frag_check = check_fragment(username)
    if frag_check is False:
        # Taken/sold/auctioned on Fragment
        return False
    elif frag_check is None:
        # Error, abort
        return None
        
    # Passed both checks!
    return True
