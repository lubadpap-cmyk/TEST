import sqlite3
from datetime import datetime, timedelta
import urllib.request
import config


def deactivate_user_traps(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE traps SET is_active = 0 WHERE user_id = ? AND is_active = 1", (user_id,))
    conn.commit()
    conn.close()


def _normalize_user_row(row):
    if row is None:
        return None

    user = dict(row)
    premium_until_value = user.get("premium_until")
    if premium_until_value:
        try:
            premium_until = datetime.fromisoformat(premium_until_value)
        except ValueError:
            premium_until = None

        if premium_until and premium_until <= datetime.utcnow():
            user["is_premium"] = 0
            user["premium_until"] = None
            user["premium_source"] = None
            user["premium_expired"] = 1
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET is_premium = 0, premium_until = NULL, premium_source = NULL WHERE user_id = ?",
                (user["user_id"],),
            )
            conn.commit()
            conn.close()
            deactivate_user_traps(user["user_id"])
        else:
            user["is_premium"] = 1
            user["premium_expired"] = 0
    else:
        user["is_premium"] = 1 if user.get("is_premium") == 1 else 0
        user["premium_expired"] = 0

    return user


def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_premium INTEGER DEFAULT 0,
        attempts_left INTEGER DEFAULT 5,
        last_reset TEXT,
        premium_until TEXT,
        premium_source TEXT DEFAULT 'none'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dictionary (
        word TEXT PRIMARY KEY
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        referrer_id INTEGER,
        new_user_id INTEGER,
        created_at TEXT NOT NULL,
        PRIMARY KEY (referrer_id, new_user_id)
    )
    """)

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN referrals_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN premium_until TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN premium_source TEXT DEFAULT 'none'")
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        "UPDATE users SET is_premium = 0, premium_until = NULL, premium_source = 'none' WHERE premium_until IS NOT NULL AND premium_until <= ?",
        (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),)
    )
    conn.commit()
    conn.close()
    populate_dictionary()


def populate_dictionary(force=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM dictionary")
    count = cursor.fetchone()[0]
    if count > 0 and not force:
        conn.close()
        return

    if force:
        print("Refreshing dictionary database (force=True)...")
        cursor.execute("DELETE FROM dictionary")
        conn.commit()
    else:
        print("Populating dictionary database...")

    sources = [
        "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa-no-swears.txt",
        "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
    ]

    words_collected = set()
    for url in sources:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8').splitlines()
                for w in data:
                    w = w.strip().lower()
                    if 3 <= len(w) <= 10 and w.isalpha():
                        words_collected.add(w)
            print(f"Fetched {len(data)} lines from {url}")
        except Exception as e:
            print(f"Failed to fetch from {url}: {e}")

    if words_collected:
        cursor.executemany("INSERT OR IGNORE INTO dictionary (word) VALUES (?)", [(w,) for w in sorted(words_collected)])
        conn.commit()
        print(f"Populated dictionary with {len(words_collected)} words from sources.")
        conn.close()
        return

    fallback_words = [
        "about", "above", "actor", "acute", "admit", "adopt", "adult", "after", "again", "agent",
        "agree", "ahead", "alarm", "album", "alert", "alike", "alive", "allow", "alone", "along",
        "alter", "among", "anger", "angle", "angry", "apart", "apple", "apply", "arena", "argue",
        "arise", "array", "arrow", "aside", "asset", "audio", "audit", "avoid", "award", "aware",
        "badly", "baker", "bases", "basic", "basis", "beach", "beard", "beast", "began", "begin",
        "begun", "being", "below", "bench", "billy", "birth", "black", "blade", "blame", "blind",
        "block", "blood", "board", "boast", "bonus", "boost", "bound", "brain", "brand", "bread",
        "break", "breed", "brief", "bring", "broad", "broke", "brown", "brush", "build", "built",
        "buyer", "cable", "calm", "camera", "camp", "canal", "candy", "canon", "cargo", "carry",
        "case", "catch", "cause", "chain", "chair", "chart", "chase", "cheap", "check", "chest",
        "chief", "child", "china", "choir", "chose", "church", "cigar", "circus", "claim", "class",
        "clean", "clear", "clerk", "click", "cliff", "climb", "clock", "close", "coach", "coast",
        "code", "coins", "color", "column", "comic", "commit", "common", "comply", "copper", "copy",
        "count", "court", "cover", "craft", "crash", "cream", "crime", "cross", "crowd", "crown",
        "cycle", "daily", "dance", "dates", "death", "debut", "delay", "depth", "devil", "diagram",
        "dialog", "diary", "dirty", "dodge", "doing", "donor", "doubt", "draft", "drama", "drawn",
        "dream", "dress", "drill", "drink", "drive", "drove", "dying", "eager", "early", "earth",
        "eight", "elbow", "elder", "elect", "elite", "empty", "enemy", "enjoy", "enter", "entry",
        "equal", "error", "event", "every", "exact", "exist", "extra", "faith", "false", "fancy",
        "fatal", "favor", "feast", "fiber", "field", "fifth", "fifty", "fight", "final", "first",
        "fixed", "flame", "flash", "fleet", "floor", "fluid", "flyer", "focus", "force", "frame",
        "frank", "fraud", "fresh", "front", "fruit", "fully", "funny", "giant", "given", "glass",
        "globe", "glory", "glove", "grace", "grade", "grand", "grant", "grass", "grave", "great",
        "green", "gross", "group", "grown", "guard", "guess", "guest", "guide", "habit", "happy",
        "harsh", "heavy", "hello", "hobby", "honey", "honor", "horse", "hotel", "house", "human",
        "index", "inner", "input", "irony", "issue", "itunes", "ivory", "jacket", "joint", "judge",
        "juice", "juror", "kappa", "karma", "keep", "kicked", "killer", "kitty", "knife", "knock",
        "known", "labor", "lemon", "logic", "lucky", "magic", "major", "match", "metal", "model",
        "money", "month", "moral", "motor", "mount", "mouse", "mouth", "movie", "music", "naked",
        "never", "newly", "night", "noise", "north", "novel", "nurse", "ocean", "offer", "often",
        "order", "other", "owner", "paint", "paper", "party", "peace", "phase", "phone", "photo",
        "piano", "piece", "pilot", "pitch", "place", "plain", "plane", "plant", "plate", "point",
        "pound", "power", "press", "price", "pride", "prime", "print", "prior", "prize", "proof",
        "proud", "prove", "queen", "quick", "quiet", "quite", "radio", "raise", "range", "rapid",
        "ratio", "reach", "react", "ready", "refer", "reply", "right", "rival", "river", "robot",
        "rough", "round", "route", "royal", "rugby", "ruler", "rural", "scale", "scene", "scope",
        "score", "scout", "screen", "screw", "script", "seize", "sense", "servo", "setup", "seven",
        "shade", "shaft", "shake", "shall", "shame", "shape", "share", "sharp", "sheep", "sheer",
        "sheet", "shelf", "shift", "shine", "shirt", "shock", "shoot", "shore", "short", "shown",
        "shrub", "sight", "sigma", "silly", "since", "sites", "sixth", "sixty", "sized", "skate",
        "skill", "skirt", "skull", "slate", "slave", "sleek", "sleep", "slide", "slope", "slots",
        "small", "smart", "smell", "smile", "smoke", "snack", "snake", "sneak", "solid", "solve",
        "sound", "south", "space", "spare", "spark", "speak", "speed", "spell", "spend", "spent",
        "split", "spoke", "sport", "spray", "squad", "stack", "staff", "stage", "stair", "strong",
        "sugar", "suite", "suits", "super", "sweet", "swept", "swift", "swing", "swiss", "sword",
        "syrup", "table", "taken", "talent", "tango", "taste", "taxes", "teach", "teeth", "tempo",
        "tenant", "tenth", "terms", "texas", "thank", "theft", "their", "theme", "there", "these",
        "thick", "thief", "thigh", "thing", "think", "third", "thirty", "those", "three", "threw",
        "throw", "thumb", "tiger", "tight", "tiles", "timer", "times", "tired", "titan", "title",
        "toast", "today", "token", "tonic", "tools", "tooth", "topic", "torch", "total", "touch",
        "tough", "tower", "toxic", "trace", "track", "trade", "trail", "train", "trait", "treat",
        "trend", "trial", "tribe", "trick", "tried", "tries", "trio", "trips", "troll", "troop",
        "truck", "truly", "trunk", "trust", "truth", "tubes", "tulip", "tumor", "tuner", "turbo",
        "turns", "tutor", "twice", "twins", "types", "ultra", "uncle", "under", "union", "unite",
        "units", "unity", "until", "upper", "upset", "urban", "usage", "users", "using", "usual",
        "vague", "valid", "value", "valve", "vapor", "vault", "vector", "venue", "venus", "verge",
        "verse", "video", "villa", "vinyl", "viral", "virus", "visit", "visor", "vista", "vital",
        "vivid", "vocal", "voice", "volts", "voter", "wagon", "waist", "walls", "wants", "warmth",
        "waste", "watch", "water", "watts", "waves", "weary", "weave", "weeks", "weigh", "weird",
        "wells", "wheel", "where", "which", "while", "white", "whole", "whose", "wider", "widow",
        "width", "winds", "windy", "wired", "wires", "wiser", "witch", "wives", "woman", "women",
        "woods", "words", "world", "worry", "worse", "worst", "worth", "would", "wound", "woven",
        "wreck", "wrist", "write", "wrong", "wrote", "yacht", "yards", "years", "yeast", "yield",
        "young", "yours", "youth", "zebra", "zones"
    ]
    cursor.executemany("INSERT OR IGNORE INTO dictionary (word) VALUES (?)", [(w,) for w in fallback_words])
    conn.commit()
    print(f"Populated dictionary with {len(fallback_words)} fallback words.")
    conn.close()


def is_word_in_dictionary(word):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM dictionary WHERE word = ?", (word.strip().lower(),))
    res = cursor.fetchone()
    conn.close()
    return res is not None


def get_random_word_by_length(length):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM dictionary WHERE length(word) = ? ORDER BY random() LIMIT 1", (length,))
    row = cursor.fetchone()
    conn.close()
    return row['word'] if row else None


def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return _normalize_user_row(user)


def add_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, is_premium, attempts_left, last_reset, language, referrals_count, premium_until, premium_source) VALUES (?, ?, 0, ?, ?, 'ru', 0, NULL, 'none')",
            (user_id, username, config.DAILY_FREE_LIMIT, today_str)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()


def reset_daily_attempts_if_needed(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if user['last_reset'] != today_str:
        cursor.execute(
            "UPDATE users SET attempts_left = ?, last_reset = ? WHERE user_id = ?",
            (config.DAILY_FREE_LIMIT, today_str, user_id)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()
    if user:
        return _normalize_user_row(user)
    return None


def use_attempt(user_id):
    user = reset_daily_attempts_if_needed(user_id)
    if not user:
        return False

    if user['is_premium'] == 1:
        return True

    if user['attempts_left'] <= 0:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET attempts_left = attempts_left - 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


def set_premium(user_id, is_premium, premium_until=None, premium_source='none', duration_days=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    val = 1 if is_premium else 0
    if is_premium and premium_until is None and duration_days is not None:
        premium_until = (datetime.utcnow() + timedelta(days=duration_days)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "UPDATE users SET is_premium = ?, premium_until = ?, premium_source = ? WHERE user_id = ?",
        (val, premium_until, premium_source, user_id)
    )
    conn.commit()
    conn.close()


def grant_referral_premium(user_id):
    now = datetime.utcnow()
    premium_until = (now + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    set_premium(user_id, True, premium_until=premium_until, premium_source='referral')


def add_trap(user_id, username):
    username = username.strip().replace("@", "").lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM traps WHERE user_id = ? AND username = ? AND is_active = 1", (user_id, username))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return False

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO traps (user_id, username, is_active, created_at) VALUES (?, ?, 1, ?)",
        (user_id, username, now_str)
    )
    conn.commit()
    conn.close()
    return True


def get_user_traps(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM traps WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['username'] for row in rows]


def remove_trap(user_id, username):
    username = username.strip().replace("@", "").lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE traps SET is_active = 0 WHERE user_id = ? AND username = ?", (user_id, username))
    conn.commit()
    conn.close()


def get_active_traps():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM traps WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows


def deactivate_trap(trap_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE traps SET is_active = 0 WHERE id = ?", (trap_id,))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]


def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM traps WHERE is_active = 1")
    active_traps = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM traps")
    total_traps = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = cursor.fetchone()[0]
    conn.close()
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "active_traps": active_traps,
        "total_traps": total_traps,
        "total_referrals": total_referrals
    }


def get_top_referrers(limit=5):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, username, referrals_count
        FROM users
        WHERE referrals_count > 0
        ORDER BY referrals_count DESC, user_id ASC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_language_distribution():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(language, 'ru') AS language, COUNT(*) AS count
        FROM users
        GROUP BY language
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return {row['language']: row['count'] for row in rows}


def set_language(user_id, lang):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()


def add_referral(referrer_id, new_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("INSERT INTO referrals (referrer_id, new_user_id, created_at) VALUES (?, ?, ?)", (referrer_id, new_user_id, now_str))
        cursor.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
