import os
import json
import time
import importlib.util
from flask import Flask, render_template, jsonify, redirect, url_for, session, request, abort
from authlib.integrations.flask_client import OAuth
import praw

# ============================================
# PATH DISCOVERY
# ============================================

def find_config_dir():
    """Auto-detect the config directory (config/ for local dev, volume-mounted in Docker)."""
    env_dir = os.environ.get('CONFIG_DIR')
    if env_dir:
        return env_dir
    base = os.path.dirname(os.path.abspath(__file__))
    for candidate in [os.path.join(base, 'config'), os.path.join(base, 'docker-config')]:
        if os.path.exists(os.path.join(candidate, 'posts.json')):
            return candidate
    return os.path.join(base, 'config')


CONFIG_DIR = find_config_dir()
POSTS_JSON = os.path.join(CONFIG_DIR, 'posts.json')
FLAIR_CACHE_JSON = os.path.join(CONFIG_DIR, 'flair_times_cache.json')
FLAIRCONFIG_PY = os.path.join(CONFIG_DIR, 'flairconfig.py')
SUBREDDIT = os.environ.get('FTMB_SUBREDDIT', '')
PORT = int(os.environ.get('FTMB_WEB_PORT', '5000'))


# === Flask & OAuth Setup ===
app = Flask(__name__)

# Use FTMB_WEB_ prefix for all webapp OAuth2 env variables
app.secret_key = os.environ.get('FTMB_WEB_SECRET_KEY', os.urandom(24))
FTMB_WEB_CLIENT_ID = os.environ.get('FTMB_WEB_CLIENT_ID', 'YOUR_CLIENT_ID')
FTMB_WEB_CLIENT_SECRET = os.environ.get('FTMB_WEB_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
FTMB_WEB_REDIRECT_URI = os.environ.get('FTMB_WEB_REDIRECT_URI', 'http://localhost:5000/auth/reddit/callback')

oauth = OAuth(app)
oauth.register(
    name='reddit',
    client_id=FTMB_WEB_CLIENT_ID,
    client_secret=FTMB_WEB_CLIENT_SECRET,
    access_token_url='https://www.reddit.com/api/v1/access_token',
    access_token_params=None,
    authorize_url='https://www.reddit.com/api/v1/authorize',
    authorize_params=None,
    api_base_url='https://oauth.reddit.com/api/v1/',
    client_kwargs={'scope': 'identity modconfig', 'token_endpoint_auth_method': 'client_secret_basic'},
)

# Helper: Check if user is a moderator
def is_moderator(username, subreddit):
    reddit = praw.Reddit(
        client_id=os.environ.get('FTMB_CLIENT_ID'),
        client_secret=os.environ.get('FTMB_CLIENT_SECRET'),
        user_agent=os.environ.get('FTMB_USER_AGENT', 'FlairTimerModBotWebappModCheck/1.0'),
        username=os.environ.get('FTMB_USERNAME'),
        password=os.environ.get('FTMB_PASSWORD'),
    )
    try:
        mods = reddit.subreddit(subreddit).moderator()
        mod_names = [str(mod).strip().lower() for mod in mods]
        print(f"[WEBAPP] Moderator usernames for r/{subreddit}: {mod_names}")
        user_name = username.strip().lower()
        print(f"[WEBAPP] Authenticating user: {user_name}")
        return user_name in mod_names
    except Exception as e:
        print(f"[WEBAPP] Error checking moderator status: {e}")
        return False


# ============================================
# DATA LOADING
# ============================================

def load_posts():
    """Load and return the raw posts.json data."""
    if not os.path.exists(POSTS_JSON):
        return {}
    try:
        with open(POSTS_JSON, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WEBAPP] Error loading posts.json: {e}")
        return {}


def load_flair_config():
    """Load flair_times and index by flair_text.

    Priority:
      1. flair_times_cache.json  — written by the bot every time it loads/reloads
         its config (wiki or fallback).  Always reflects what the bot is using.
      2. flairconfig.py          — static fallback for local dev without a running bot.
    Returns a dict of {flair_text: config_dict} and a string indicating the source.
    """
    # 1. Try the live cache written by the bot
    if os.path.exists(FLAIR_CACHE_JSON):
        try:
            with open(FLAIR_CACHE_JSON, 'r') as f:
                flair_list = json.load(f)
            if isinstance(flair_list, list) and flair_list:
                return (
                    {ft['flair_text']: ft for ft in flair_list if 'flair_text' in ft},
                    'cache'
                )
        except Exception as e:
            print(f"[WEBAPP] Error reading flair_times_cache.json: {e}")

    # 2. Fall back to flairconfig.py
    if os.path.exists(FLAIRCONFIG_PY):
        try:
            spec = importlib.util.spec_from_file_location('_flairconfig_web', FLAIRCONFIG_PY)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            flair_list = getattr(mod, 'flair_times', [])
            return (
                {ft['flair_text']: ft for ft in flair_list if 'flair_text' in ft},
                'flairconfig.py'
            )
        except Exception as e:
            print(f"[WEBAPP] Error loading flairconfig.py: {e}")

    return {}, 'none'


def build_post_list():
    """Build a flat list of post dicts from posts.json, enriched with timer info."""
    posts_data = load_posts()
    flair_cfg, _ = load_flair_config()
    now = time.time()
    result = []

    for flair_text, data in posts_data.items():
        # Support both old format {id: ts} and new format {tracking: {id: ts}, processed: [...]}
        if isinstance(data, dict) and ('tracking' in data or 'processed' in data):
            tracking = data.get('tracking', {})
            processed_ids = set(data.get('processed', []))
        else:
            tracking = data if isinstance(data, dict) else {}
            processed_ids = set()

        cfg = flair_cfg.get(flair_text, {})
        hours = cfg.get('hours')
        action = cfg.get('action')

        for post_id, start_ts in tracking.items():
            if hours is not None:
                trigger_ts = start_ts + hours * 3600
                secs_remaining = trigger_ts - now
            else:
                trigger_ts = None
                secs_remaining = None

            result.append({
                'id': post_id,
                'flair': flair_text,
                'status': 'processed' if post_id in processed_ids else 'tracking',
                'start_time': start_ts,
                'trigger_time': trigger_ts,
                'seconds_remaining': secs_remaining,
                'hours_config': hours,
                'action': action,
            })

        # Processed posts not currently in tracking
        for post_id in processed_ids:
            if post_id not in tracking:
                result.append({
                    'id': post_id,
                    'flair': flair_text,
                    'status': 'processed',
                    'start_time': None,
                    'trigger_time': None,
                    'seconds_remaining': None,
                    'hours_config': hours,
                    'action': action,
                })

    return result


# ============================================
# ROUTES
# ============================================


# === Auth-protected dashboard ===
@app.route('/')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    if not is_moderator(user['name'], SUBREDDIT):
        return abort(403, description="You must be a moderator to view this page.")
    return render_template('dashboard.html', subreddit=SUBREDDIT, user=user)

# === Reddit OAuth2 routes ===
@app.route('/login')
def login():
    return oauth.reddit.authorize_redirect(FTMB_WEB_REDIRECT_URI)

@app.route('/auth/reddit/callback')
def auth_callback():
    token = oauth.reddit.authorize_access_token()
    user = oauth.reddit.get('https://oauth.reddit.com/api/v1/me', token=token).json()
    session['user'] = user
    session['token'] = token
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/posts')
def api_posts():
    posts = build_post_list()
    # Default sort: tracking first, then by seconds_remaining ascending (most urgent first)
    posts.sort(key=lambda x: (
        0 if x['status'] == 'tracking' else 1,
        x['seconds_remaining'] if x['seconds_remaining'] is not None else float('inf'),
    ))
    return jsonify(posts)


@app.route('/api/stats')
def api_stats():
    posts_data = load_posts()
    flair_cfg, config_source = load_flair_config()
    now = time.time()

    total_tracking = 0
    total_processed = 0
    total_overdue = 0
    flair_counts = {}

    for flair_text, data in posts_data.items():
        if isinstance(data, dict) and ('tracking' in data or 'processed' in data):
            tracking = data.get('tracking', {})
            processed_ids = set(data.get('processed', []))
        else:
            tracking = data if isinstance(data, dict) else {}
            processed_ids = set()

        total_tracking += len(tracking)
        total_processed += len(processed_ids)

        hours = flair_cfg.get(flair_text, {}).get('hours')
        if hours is not None:
            for start_ts in tracking.values():
                if now > start_ts + hours * 3600:
                    total_overdue += 1

        if tracking:
            flair_counts[flair_text] = len(tracking)

    return jsonify({
        'total_tracking': total_tracking,
        'total_processed': total_processed,
        'total_overdue': total_overdue,
        'active_flairs': len(flair_counts),
        'flair_counts': flair_counts,
        'posts_file_exists': os.path.exists(POSTS_JSON),
        'config_source': config_source,
        'cache_file_exists': os.path.exists(FLAIR_CACHE_JSON),
    })


@app.route('/api/flairs')
def api_flairs():
    return jsonify(sorted(load_posts().keys()))


# ============================================
# ENTRY POINT
# ============================================

if __name__ == '__main__':
    print(f"[WEBAPP] FlairTimerModBot Dashboard starting on port {PORT}")
    print(f"[WEBAPP] Config dir : {CONFIG_DIR}")
    print(f"[WEBAPP] Posts file : {POSTS_JSON}")
    print(f"[WEBAPP] Cache file : {FLAIR_CACHE_JSON}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
