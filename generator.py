import random
import string
import re
import db

VOWELS = "aeiou"
CONSONANTS = "".join(c for c in string.ascii_lowercase if c not in VOWELS)

# Common 2-letter syllables/words for prefix/suffix combination
COMMON_2_LETTER_WORDS = [
    "my", "go", "to", "it", "is", "am", "me", "we", "he", "up", "so", 
    "no", "on", "by", "at", "in", "if", "do", "or", "an", "re", "ex"
]

RARE_USERNAME_BANK = {
    5: [
        "azrul", "cyran", "lyrix", "qorin", "sylph", "vexon", "xyral", "zorin", "thyra",
        "myrix", "kylor", "novex", "jexan", "ryxen", "vynor", "gylor", "fexon", "halyr",
        "cyron", "zavyn", "quorin", "xalor", "myrul", "dovyn", "rython", "lyrion", "sovax",
        "velyn", "qyren", "zavik"
    ],
    6: [
        "azrulx", "cyrand", "lyrixe", "qorinn", "sylphx", "vexora", "xyraln", "zorina",
        "thyrax", "myrixo", "kylorn", "novexa", "jexand", "ryxena", "vynora", "gylorn",
        "fexona", "halyra", "cyrona", "zavynx", "quorin", "xalorn", "myrulx", "dovynx",
        "rython", "lyriona", "velynx", "qyrenz", "sovaxe"
    ]
}

ULTRA_RARE_PREFIXES = ["xyr", "qor", "vyn", "lyr", "zex", "fyr", "syn", "taz", "kyx", "zyl"]
ULTRA_RARE_SUFFIXES = ["x", "n", "r", "l", "th", "ix", "or", "en", "us", "ys"]

RARE_USERNAME_SET = set(name for names in RARE_USERNAME_BANK.values() for name in names)

THEME_ROOTS = {
    'crypto': ["coin", "ton", "crypt", "pay", "bit", "dex", "swap", "nft", "dao", "web"],
    'gaming': ["play", "game", "frag", "gg", "pro", "bot", "win", "aim", "pvp", "mod"],
    'aesthetics': ["star", "moon", "sky", "soul", "art", "luv", "sad", "sun", "aura", "vib"]
}

def is_ultra_rare_username(username):
    username = username.lower()
    return (
        any(username.startswith(prefix) for prefix in ULTRA_RARE_PREFIXES) and
        any(username.endswith(suffix) for suffix in ULTRA_RARE_SUFFIXES)
    )


def generate_username(length=5, include_digits=False):
    """
    Generates a random username.
    Telegram usernames must start with a letter and can contain letters and digits.
    """
    if length < 5:
        length = 5
        
    first_char = random.choice(string.ascii_lowercase)
    
    if include_digits:
        chars = string.ascii_lowercase + string.digits
    else:
        chars = string.ascii_lowercase
        
    remaining = "".join(random.choice(chars) for _ in range(length - 1))
    return first_char + remaining

def generate_pronounceable_username(length=5, include_digits=False):
    """Create a rare-looking but pronounceable username from a curated bank."""
    if length < 5:
        length = 5

    candidates = RARE_USERNAME_BANK.get(length, [])
    if candidates:
        username = random.choice(candidates)
    else:
        prefix = random.choice(["xyl", "syl", "qor", "vyn", "lyr", "zor", "myr", "kyl", "jex", "fex"])
        suffix = random.choice(["ion", "an", "ix", "or", "yn", "ex", "en", "ar", "yl", "us"])
        vowel = random.choice("aeiouy")
        username = prefix + vowel + suffix
        if len(username) < length:
            username += random.choice("nrxls")
        username = username[:length]

    if include_digits and random.random() < 0.35:
        insert_pos = random.randint(1, max(1, len(username) - 1))
        username = username[:insert_pos] + random.choice(string.digits) + username[insert_pos:]

    return username[:length]


def generate_ultra_rare_username(length=5, include_digits=False):
    """Generate a premium-style username for the highest rarity level."""
    if length < 5:
        length = 5

    prefix = random.choice(["xyr", "qor", "vyn", "lyr", "zex", "fyr", "syn", "taz", "kyx", "zyl"])
    vowel = random.choice("aeiouy")
    suffix = random.choice(["x", "n", "r", "l", "th", "ix", "or", "en", "us", "ys"])
    username = (prefix + vowel + suffix)[:length]

    if len(username) < length:
        username += random.choice(string.ascii_lowercase)

    if include_digits and random.random() < 0.4:
        pos = random.randint(1, max(1, len(username) - 2))
        username = username[:pos] + random.choice("79") + username[pos:]

    return username[:length]

def generate_compound_word(length):
    """Generate a 7 or 8 letter username by combining two dictionary words."""
    if length == 7:
        lengths = random.choice([(3, 4), (4, 3)])
    elif length == 8:
        lengths = random.choice([(4, 4), (3, 5), (5, 3)])
    else:
        return generate_username(length)
        
    word1 = db.get_random_word_by_length(lengths[0])
    word2 = db.get_random_word_by_length(lengths[1])
    
    if not word1 or not word2:
        return generate_username(length)
        
    return word1 + word2

def generate_thematic(theme, length):
    """Generate a username based on a specific theme."""
    roots = THEME_ROOTS.get(theme, THEME_ROOTS['aesthetics'])
    root = random.choice(roots)
    
    # We need to fill the rest of the length
    rem_len = length - len(root)
    if rem_len <= 0:
        return root[:length]
        
    # Append or prepend a random dictionary word of the remaining length
    other_word = db.get_random_word_by_length(rem_len)
    if other_word:
        return random.choice([root + other_word, other_word + root])
    
    # Fallback to random letters if no word found
    suffix = "".join(random.choice(string.ascii_lowercase) for _ in range(rem_len))
    return root + suffix


# Popular short suffixes and prefixes to combine with user words
WORD_SUFFIXES = ["x", "z", "pro", "xo", "vip", "gg", "ok", "hi", "io",
                 "yt", "tv", "up", "go", "on", "er", "ly", "fy", "hub",
                 "lab", "dev", "art", "sky", "sun", "run", "one", "way"]
WORD_PREFIXES = ["the", "i", "my", "its", "get", "hey", "top", "real",
                 "og", "pro", "mr", "dr", "im", "not", "xo", "by"]

def generate_with_word(word):
    """Generate a username based on a user-provided word/keyword."""
    word = word.strip().lower()
    word = ''.join(c for c in word if c.isalnum())  # keep only alphanumeric
    
    if not word:
        return None

    # Strategy 1: word + short suffix
    # Strategy 2: short prefix + word
    # Strategy 3: word + dictionary word
    # Strategy 4: dictionary word + word
    # Strategy 5: word + 1-2 digits
    strategy = random.randint(1, 5)
    
    if strategy == 1:
        sfx = random.choice(WORD_SUFFIXES)
        result = word + sfx
    elif strategy == 2:
        pfx = random.choice(WORD_PREFIXES)
        result = pfx + word
    elif strategy == 3:
        rem = max(3, 8 - len(word))
        other = db.get_random_word_by_length(rem)
        result = word + (other if other else random.choice(WORD_SUFFIXES))
    elif strategy == 4:
        rem = max(3, 8 - len(word))
        other = db.get_random_word_by_length(rem)
        result = (other if other else random.choice(WORD_PREFIXES)) + word
    else:
        digits = str(random.randint(0, 99))
        result = word + digits

    # Ensure length is valid (5–32 chars for Telegram)
    result = result[:32]
    if len(result) < 5:
        result = result + random.choice(WORD_SUFFIXES)
    
    return result


def generate_by_rating(length=5, rating=7, include_digits=False):
    """
    Smart generator that constructs a username aiming for a specific rarity rating:
      - 10: Ultra-rare coined username with premium letters
      - 9: Rare pronounceable username that still looks fresh
      - 8 / 7: Unique pronounceable names with some structure
    - Fallback: Standard random generation
    """
    if length >= 7:
        username = generate_compound_word(length)
        if include_digits:
            pos = random.randint(1, len(username) - 1)
            username = username[:pos] + random.choice(string.digits) + username[pos:]
            username = username[:length]
        return username

    if rating == 10:
        return generate_ultra_rare_username(length, include_digits)

    elif rating == 9:
        return generate_pronounceable_username(length, include_digits)

    elif rating in [7, 8]:
        return generate_pronounceable_username(length, include_digits)

    # Fallback / Low ratings: Standard generation
    return generate_username(length, include_digits)

def generate_from_mask(mask):
    """
    Generates a username based on a mask.
    Mask notation:
      ? = random letter (a-z)
      # = random digit (0-9)
      * = random letter or digit
      Any other character = itself
    Enforces Telegram's rule that the first character must be a letter.
    """
    result = []
    for i, char in enumerate(mask):
        if char == '?':
            result.append(random.choice(string.ascii_lowercase))
        elif char == '#':
            if i == 0:
                result.append(random.choice(string.ascii_lowercase))
            else:
                result.append(random.choice(string.digits))
        elif char == '*':
            if i == 0:
                result.append(random.choice(string.ascii_lowercase))
            else:
                result.append(random.choice(string.ascii_lowercase + string.digits))
        else:
            result.append(char.lower())
            
    username = "".join(result)
    username = re.sub(r'[^a-z0-9_]', '', username)
    return username

def rate_username(username):
    """
    Rates a username on a scale of 1 to 10 using DB lookup & pronunciation heuristics:
      - 10 = Ultra-rare coined username with premium characters
      - 9 = Compound or rare pronounceable username
      - 7/8 = Starts or ends with a real word or has a good pattern
      - 1 to 6 = Common words, simple text or poor letter combinations
    """
    username = username.lower().replace("@", "")
    length = len(username)
    
    is_exact_word = False
    try:
        if db.is_word_in_dictionary(username):
            is_exact_word = True
    except Exception as e:
        print(f"Error checking exact dictionary match: {e}")
        
    # 2. Check for compound words (split in two parts and check if both are in db)
    try:
        if length >= 5:
            for split in range(2, length - 1):
                part1 = username[:split]
                part2 = username[split:]
                if (db.is_word_in_dictionary(part1) or part1 in COMMON_2_LETTER_WORDS) and db.is_word_in_dictionary(part2):
                    return 9
                if db.is_word_in_dictionary(part1) and (db.is_word_in_dictionary(part2) or part2 in COMMON_2_LETTER_WORDS):
                    return 9
    except Exception as e:
        print(f"Error checking compound dictionary match: {e}")
        
    # 3. Check if starts/ends with a dictionary word of length >= 3
    has_word_part = False
    try:
        for split in range(3, length + 1):
            w_start = username[:split]
            w_end = username[length - split:]
            if db.is_word_in_dictionary(w_start) or db.is_word_in_dictionary(w_end):
                has_word_part = True
                break
    except Exception as e:
        print(f"Error checking partial dictionary match: {e}")

    # Standard character heuristics
    score = 1
    
    # Length bonus
    if length <= 4:
        score += 3
    elif length == 5:
        score += 2
    elif length == 6:
        score += 1
        
    # Alternating vowels and consonants (syllabic/pronounceable)
    alternations = 0
    for i in range(length - 1):
        c1, c2 = username[i], username[i+1]
        if (c1 in VOWELS and c2 in CONSONANTS) or (c1 in CONSONANTS and c2 in VOWELS):
            alternations += 1
    if alternations >= length - 2:
        score += 2
        
    # Palindrome / Symmetry
    if username == username[::-1]:
        score += 3
        
    # Double letters (e.g. 'll', 'oo')
    double_letters = 0
    for i in range(length - 1):
        if username[i] == username[i+1] and username[i].isalpha():
            double_letters += 1
    if double_letters > 0:
        score += 1
        if double_letters > 1:
            score += 1
            
    # Pattern repetition (e.g. 'abab')
    if length >= 4:
        first_two = username[:2]
        if username.startswith(first_two * 2) or (length >= 5 and username[1:5] == username[1:3] * 2):
            score += 2
            
    # Digits evaluation
    has_digits = any(char.isdigit() for char in username)
    if not has_digits:
        score += 2
    else:
        # Nice ending digits (777, 000, 123)
        nice_digits = [r'777$', r'000$', r'123$', r'007$', r'888$']
        if any(re.search(pat, username) for pat in nice_digits):
            score += 1
            
    # Add partial word bonus
    if has_word_part:
        score += 2

    # Rare-looking coined usernames should score higher
    if username in RARE_USERNAME_SET:
        score += 2
    if is_ultra_rare_username(username):
        score += 3
    if any(char in "qxyz" for char in username):
        score += 1
    if username.endswith(("x", "r", "n", "l", "s", "k")):
        score += 1

    if is_exact_word:
        score = min(score, 8)
    elif is_ultra_rare_username(username):
        score = max(score, 10)

    score = max(1, min(10, score))
    return score
