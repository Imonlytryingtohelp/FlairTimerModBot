
import praw
import os
import os.path
import json
import time
import yaml
import threading
from prawcore.exceptions import ResponseException
from update_checker import start_update_checker

# ============================================
# BOT CONFIGURATION
# ============================================
BOT_NAME = "FlairTimerModBot"
BOT_VERSION = "1.7.0"
WIKI_PAGE = os.environ.get("FTMB_WIKI_PAGE", "flair-timers")  # Wiki page with flair timer configs
USE_WIKI_CONFIG = os.environ.get("FTMB_USE_WIKI_CONFIG", "true").lower() == "true"
# ============================================


# Helper to get env var or default
def env_or_default(var, default):
    return os.environ.get(var, default)


# Create config/config.py from environment if missing or empty
default_config_path = os.path.join('config', 'config.py')


def write_config_from_env():
    os.makedirs('config', exist_ok=True)
    with open(default_config_path, 'w') as f:
        f.write(
            f'username = "{env_or_default("FTMB_USERNAME", "")}"\n'
            f'password = "{env_or_default("FTMB_PASSWORD", "")}"\n'
            f'client_id = "{env_or_default("FTMB_CLIENT_ID", "")}"\n'
            f'client_secret = "{env_or_default("FTMB_CLIENT_SECRET", "")}"\n'
            f'user_agent = "{env_or_default("FTMB_USER_AGENT", "Flair Timer Mod Bot")}"\n'
            '\n'
            f'subreddit = "{env_or_default("FTMB_SUBREDDIT", "")}"\n'
            f'interval = {env_or_default("FTMB_INTERVAL", "30")}\n'
            f'searchlimit = {env_or_default("FTMB_SEARCHLIMIT", "600")}\n'
        )
    print(f"Configuration file auto-populated from environment variables at {default_config_path}.")


# Check if config file exists and is non-empty, else generate from env
def config_needs_populating():
    if not os.path.exists(default_config_path):
        return True
    try:
        with open(default_config_path, 'r') as f:
            content = f.read().strip()
            return len(content) == 0
    except Exception:
        return True


if config_needs_populating():
    write_config_from_env()


# Import main config
from config import config


def load_flair_times_from_wiki(reddit, subreddit_name):
    """Load flair timer configs from subreddit wiki page (YAML format)."""
    try:
        wiki_page = reddit.subreddit(subreddit_name).wiki[WIKI_PAGE]
        yaml_content = wiki_page.content_md
        flair_times = yaml.safe_load(yaml_content)
        
        if not isinstance(flair_times, list):
            print(f"[WIKI] Error: Wiki page content is not a YAML list")
            return []
        
        print(f"[WIKI] Successfully loaded {len(flair_times)} flair timer configs from r/{subreddit_name}/wiki/{WIKI_PAGE}")
        return flair_times
    except Exception as e:
        print(f"[WIKI] Error loading wiki page: {e}")
        print(f"[WIKI] Make sure the wiki page exists at r/{subreddit_name}/wiki/{WIKI_PAGE}")
        return []


# Create default flairconfig.py as fallback
flair_config_path = os.path.join('config', 'flairconfig.py')


def write_default_flairconfig():
    if not os.path.exists(flair_config_path):
        os.makedirs(os.path.dirname(flair_config_path), exist_ok=True)
        with open(flair_config_path, 'w') as f:
            f.write('# flairconfig.py\n')
            f.write('# DEPRECATED: This file is used as fallback if wiki loading is disabled.\n')
            f.write('# Flair timers are now loaded from the subreddit wiki page.\n')
            f.write('# Actions: "comment" (post a comment), "modmail" (send modmail), or "both"\n')
            f.write('flair_times = [\n')
            f.write('    {\n')
            f.write('        "flair_text": "Waiting for OP",\n')
            f.write('        "hours": 48,\n')
            f.write('        "action": "comment",\n')
            f.write('        "comment_message": "This post has had the \'Waiting for OP\' flair for 48 hours.",\n')
            f.write('        "messagetitle": "Modmail Notification",\n')
            f.write('        "lock_post": False,\n')
            f.write('        "distinguish_sticky": False\n')
            f.write('    },\n')
            f.write(']\n')
        print(f"Default flairconfig.py created at {flair_config_path}.")


write_default_flairconfig()


# Load flair_times from flairconfig.py (fallback)
import importlib.util
spec = importlib.util.spec_from_file_location("flairconfig", flair_config_path)
flairconfig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flairconfig)
flair_times_fallback = getattr(flairconfig, "flair_times", [])
flair_times = []  # Will be populated after authentication


def chat_message_watcher(reddit, subreddit_name, startup_timestamp):
    """Monitor modmail for reload-flairtimers command from moderators.
    
    Only processes messages created after bot startup to prevent reprocessing on restart.
    """
    global flair_times
    
    chat_requests_file = os.path.join(os.path.dirname(__file__), 'DB', 'chat_reload_requests.txt')
    processed_message_ids = set()
    
    # Load processed IDs
    if os.path.exists(chat_requests_file):
        with open(chat_requests_file, 'r') as f:
            for line in f:
                processed_message_ids.add(line.strip())
    
    print(f"[CHAT_WATCHER] Started - monitoring for 'reload-flairtimers' commands (startup: {startup_timestamp})")
    
    while True:
        try:
            for message in reddit.inbox.stream():
                if not hasattr(message, 'id') or message.id in processed_message_ids:
                    continue
                
                # Check if message was created AFTER bot startup
                # message.created_utc is a Unix timestamp (seconds since epoch)
                if hasattr(message, 'created_utc') and message.created_utc < startup_timestamp:
                    print(f"[CHAT_WATCHER] Skipping message {message.id} (created before startup)")
                    processed_message_ids.add(message.id)
                    os.makedirs(os.path.dirname(chat_requests_file), exist_ok=True)
                    with open(chat_requests_file, 'a') as f:
                        f.write(message.id + '\n')
                    continue
                
                processed_message_ids.add(message.id)
                os.makedirs(os.path.dirname(chat_requests_file), exist_ok=True)
                with open(chat_requests_file, 'a') as f:
                    f.write(message.id + '\n')
                
                # Check for reload-flairtimers command
                if hasattr(message, 'body') and 'reload-flairtimers' in message.body.lower():
                    author = getattr(message, 'author', None)
                    
                    # Verify moderator
                    if author and author in reddit.subreddit(subreddit_name).moderator():
                        print(f"[CHAT_WATCHER] Reload command from moderator {author}")
                        
                        # Reload wiki config
                        new_flair_times = load_flair_times_from_wiki(reddit, subreddit_name)
                        if new_flair_times:
                            flair_times = new_flair_times
                            save_flair_times_cache(flair_times)
                            reply_text = f"✅ Successfully reloaded flair timer configs from wiki. Loaded {len(flair_times)} configurations."
                            print("[CHAT_WATCHER] Config reloaded successfully")
                        else:
                            reply_text = "❌ Failed to reload flair timer configs from wiki. Check the wiki page and try again."
                            print("[CHAT_WATCHER] Config reload failed")
                        
                        try:
                            message.reply(reply_text)
                        except Exception as e:
                            print(f"[CHAT_WATCHER] Error replying to message: {e}")
        except Exception as e:
            print(f"[CHAT_WATCHER] Error in watcher loop: {e}")
            time.sleep(30)


def save_flair_times_cache(flair_times_list):
    """Write the active flair_times to a JSON cache for the dashboard webapp.
    
    Called every time flair_times is loaded or reloaded so the webapp always
    reflects the exact config the bot is currently using.
    """
    cache_path = os.path.join('config', 'flair_times_cache.json')
    try:
        os.makedirs('config', exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(flair_times_list, f, indent=2)
        print(f"[CACHE] Saved {len(flair_times_list)} flair timer configs to {cache_path}")
    except Exception as e:
        print(f"[CACHE] Error saving flair times cache: {e}")


def send_modmail_with_backoff(reddit, subreddit_name, subject, message, max_retries=4):
    """Send modmail with exponential backoff for rate limiting.
    
    Respects Retry-After header and RATELIMIT error messages from Reddit.
    Falls back to exponential backoff if no wait time specified.
    Returns True if successful, False otherwise.
    """
    wait_times = [5, 10, 20, 60]  # Fallback wait times in seconds
    
    for attempt in range(max_retries):
        try:
            data = {
                "subject": subject,
                "text": message,
                "to": f"/r/{subreddit_name}",
            }
            reddit.post("api/compose/", data=data)
            print(f"[MODMAIL] Sent successfully")
            return True
        except ResponseException as e:
            if e.response.status_code == 429:
                # Rate limited - check for Retry-After header
                retry_after = e.response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                        print(f"[MODMAIL] Rate limited (attempt {attempt + 1}/{max_retries}). Reddit says wait {wait_time}s...")
                    except ValueError:
                        # Retry-After might be an HTTP date, fall back to our times
                        wait_time = wait_times[attempt] if attempt < len(wait_times) else 60
                        print(f"[MODMAIL] Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s before retry...")
                else:
                    # No Retry-After header, use our fallback times
                    wait_time = wait_times[attempt] if attempt < len(wait_times) else 60
                    print(f"[MODMAIL] Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s before retry...")
                
                time.sleep(wait_time)
            else:
                print(f"[MODMAIL] HTTP error {e.response.status_code}: {e}")
                return False
        except Exception as e:
            # Check if it's a RATELIMIT error (Reddit API returns this as an exception message)
            error_str = str(e)
            if "RATELIMIT" in error_str:
                # Try to extract wait time from error message like:
                # "RATELIMIT: Looks like you've been doing that a lot. Take a break for 126 seconds before trying again."
                import re
                match = re.search(r'(\d+)\s+seconds?', error_str)
                if match:
                    wait_time = int(match.group(1))
                    print(f"[MODMAIL] Rate limited (attempt {attempt + 1}/{max_retries}). Reddit says wait {wait_time}s...")
                else:
                    # Couldn't parse wait time, use fallback
                    wait_time = wait_times[attempt] if attempt < len(wait_times) else 60
                    print(f"[MODMAIL] Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s before retry...")
                
                time.sleep(wait_time)
            else:
                # Other error type
                print(f"[MODMAIL] Error: {e}")
                return False
    
    print(f"[MODMAIL] Failed after {max_retries} retries")
    return False


def authentication():
    print("Authenticating...")
    reddit = praw.Reddit(
        username=config.username,
        password=config.password,
        client_id=config.client_id,
        client_secret=config.client_secret,
        user_agent=config.user_agent
    )
    print("Authenticated as {}.".format(reddit.user.me()))
    print(f"Monitoring subreddit: /r/{config.subreddit}")
    return reddit


def main(reddit, all_posts: dict):
    # all_posts structure: {flair_text: {"tracking": {submission_id: timestamp}, "processed": [submission_id, ...]}}
    while True:
        # OPTIMIZATION: Scan new posts once and process all flair configs against them
        print(f"[SCAN] Scanning {config.searchlimit} newest posts for all configured flairs")
        scanned_ids = set()
        submission_cache = {}  # Cache submissions to avoid re-fetching
        
        try:
            for submission in reddit.subreddit(config.subreddit).new(limit=config.searchlimit):
                scanned_ids.add(submission.id)
                submission_cache[submission.id] = submission
                current_flair = submission.link_flair_text
                
                print(f"DEBUG: Scanning post {submission.id} | flair='{current_flair}'")
                
                # Check this submission against all flair configs
                for flair_cfg in flair_times:
                    flair_text = flair_cfg["flair_text"]
                    
                    # Ensure new structure for this flair
                    if flair_text not in all_posts:
                        all_posts[flair_text] = {"tracking": {}, "processed": []}
                    elif "tracking" not in all_posts[flair_text]:
                        # Shouldn't happen due to migration, but just in case
                        all_posts[flair_text] = {"tracking": all_posts[flair_text], "processed": []}
                    
                    tracking = all_posts[flair_text]["tracking"]
                    processed = all_posts[flair_text]["processed"]
                    
                    # If post was processed for this flair, check if flair changed
                    if submission.id in processed:
                        if current_flair != flair_text:
                            # Flair changed! Remove from processed so we can action it again if set back
                            print(f"DEBUG: Post {submission.id} flair changed from '{flair_text}' to '{current_flair}', removing from processed")
                            processed.remove(submission.id)
                        else:
                            # Flair is still the same, skip (already actioned once)
                            print(f"DEBUG: Post {submission.id} already processed for flair '{flair_text}', skipping")
                            continue
                    
                    # Add new posts with matching flair (that haven't been processed)
                    if submission.id not in tracking and current_flair == flair_text:
                        print(f"DEBUG: Adding post {submission.id} to tracking for flair '{flair_text}'")
                        tracking[submission.id] = time.time()
                        print(f"Post {submission.id} has been flaired {flair_text}")
                    
                    # Remove posts that no longer have the matching flair
                    elif submission.id in tracking and current_flair != flair_text:
                        print(f"DEBUG: Removing post {submission.id} from tracking (flair changed to '{current_flair}')")
                        tracking.pop(submission.id)
                        print(f"Post {submission.id} has been unflaired {flair_text}")
        
        except Exception as e:
            print(f"[SCAN] Error scanning new posts: {e}")
        
        # OPTIMIZATION: Process expirations for each flair config
        for flair_cfg in flair_times:
            flair_text = flair_cfg["flair_text"]
            hours = flair_cfg["hours"]
            action = flair_cfg.get("action", "comment")
            comment_message = flair_cfg.get("comment_message", "")
            messagetitle = flair_cfg.get("messagetitle", "Modmail Notification")
            lock_post = flair_cfg.get("lock_post", False)
            distinguish_sticky = flair_cfg.get("distinguish_sticky", False)
            
            if flair_text not in all_posts:
                continue
            
            tracking = all_posts[flair_text].get("tracking", {})
            processed = all_posts[flair_text].get("processed", [])
            
            # Find expired posts for this flair
            expired = []
            current_time = time.time()
            for submission_id, flair_time in tracking.items():
                if current_time > flair_time + (hours * 60 * 60):
                    expired.append(submission_id)
            
            # Process each expired post
            for submission_id in expired:
                # Try to use cached submission first
                if submission_id in submission_cache:
                    subm = submission_cache[submission_id]
                else:
                    # Only fetch if not in cache (older post)
                    try:
                        subm = reddit.submission(submission_id)
                    except Exception as e:
                        print(f"Could not fetch expired post {submission_id}: {e}")
                        tracking.pop(submission_id, None)
                        continue
                
                # Check if flair still matches (in case it changed)
                if subm.link_flair_text != flair_text:
                    print(f"Post {submission_id} flair changed to '{subm.link_flair_text}', removing from tracking")
                    tracking.pop(submission_id, None)
                    continue
                
                # Handle comment action
                if action in ["comment", "both"]:
                    try:
                        if lock_post:
                            try:
                                subm.mod.lock()
                            except Exception as e:
                                print(f"Could not lock submission: {e}")

                        comment = subm.reply(body=comment_message)
                        try:
                            if distinguish_sticky:
                                comment.mod.distinguish(how="yes", sticky=True)
                            else:
                                comment.mod.distinguish(how="yes")
                            print(f"Distinguished comment (sticky={distinguish_sticky})")
                        except Exception as e:
                            print(f"Could not distinguish comment: {e}")
                        print(f"Post {submission_id} has been flaired {flair_text} for {hours} hours, posted comment")
                    except Exception as e:
                        print(f"Error posting comment on {submission_id}: {e}")

                # Handle modmail action
                if action in ["modmail", "both"]:
                    try:
                        message = f"It has been {hours/24} day/s since this was flaired [{flair_text}](https://old.reddit.com{subm.permalink})"
                        send_modmail_with_backoff(reddit, config.subreddit, messagetitle, message)
                        print(f"Post {submission_id} has been flaired {flair_text} for {hours} hours, sent modmail")
                        # Longer sleep after modmail to avoid rate limiting (Reddit is strict with modmail)
                        time.sleep(10)
                    except Exception as e:
                        print(f"Error sending modmail for {submission_id}: {e}")

                # Wait briefly after action (comments don't need as much delay)
                if action == "comment":
                    time.sleep(2)
                elif action == "both":
                    # Already waited 10s for modmail, minimal additional wait needed
                    time.sleep(1)

                # Mark as processed and remove from tracking
                tracking.pop(submission_id, None)
                if submission_id not in processed:
                    processed.append(submission_id)
                    print(f"Post {submission_id} marked as processed for flair '{flair_text}'")
        
        save_posts(all_posts)
        print(f"[CYCLE] Sleeping for {config.interval} seconds")
        time.sleep(config.interval)


def load_posts():
    if not os.path.exists("config/posts.json"):
        with open("config/posts.json", "w+") as file:
            json.dump({}, file)
    
    with open("config/posts.json", "r+") as file:
        data = json.load(file)
        
        if not isinstance(data, dict):
            return {}
        
        # MIGRATION: Convert old format {flair: {post_id: timestamp}} to new format
        # New format: {flair: {"tracking": {...}, "processed": [...]}}
        migrated = False
        for flair_text in list(data.keys()):
            flair_data = data[flair_text]
            
            # If this flair uses old format (direct post_id dict)
            if isinstance(flair_data, dict) and "tracking" not in flair_data:
                # Check if it has any post IDs (all keys are non-string or are timestamps)
                has_post_ids = any(isinstance(v, (int, float)) for v in flair_data.values())
                if has_post_ids:
                    # Migrate to new format
                    print(f"[MIGRATION] Converting flair '{flair_text}' to new format")
                    data[flair_text] = {
                        "tracking": flair_data,
                        "processed": []
                    }
                    migrated = True
        
        if migrated:
            # Save migrated data
            with open("config/posts.json", "w") as file:
                json.dump(data, file)
            print("[MIGRATION] Completed posts.json migration")
        
        return data


def save_posts(data):
    with open('config/posts.json', 'w+') as file:
        json.dump(data, file)


# Authenticate once at startup
reddit = authentication()

# Capture startup timestamp (in Unix seconds) for chat watcher
startup_timestamp = time.time()
print(f"[STARTUP] Bot started at timestamp {startup_timestamp}")

# Load flair times from wiki or fallback to file
if USE_WIKI_CONFIG:
    flair_times = load_flair_times_from_wiki(reddit, config.subreddit)
    if not flair_times:
        print("[WIKI] Failed to load wiki config, falling back to flairconfig.py")
        flair_times = flair_times_fallback
else:
    print("[CONFIG] Using local flairconfig.py (wiki loading disabled)")
    flair_times = flair_times_fallback

if not flair_times:
    print("[ERROR] No flair timer configs loaded. Bot cannot continue.")
    exit(1)

# Write active config to cache so the dashboard webapp always shows the live values
save_flair_times_cache(flair_times)

# Start chat message watcher in background thread with startup timestamp
chat_watcher_thread = threading.Thread(
    target=chat_message_watcher,
    args=(reddit, config.subreddit, startup_timestamp),
    daemon=True
)
chat_watcher_thread.start()

# Start update checker in background
start_update_checker(reddit, config.subreddit, BOT_NAME, BOT_VERSION)

# Main bot loop
while True:
    try:
        posts = load_posts()
        main(reddit=reddit, all_posts=posts)
    except ResponseException as e:
        if e.response.status_code == 429:
            print("Rate limited by Reddit. Waiting before retry...")
        else:
            print(f"Reddit API error: {e}")
        time.sleep(5)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
