
# Flair Timer Mod Bot

A unified Reddit bot that monitors a subreddit for posts with specific link flairs. When a post maintains a flair for a configured duration, the bot can:

1. **Post a comment** - Leave a configured message with optional:
   - Post locking
   - Comment distinction (with optional sticky)
2. **Send modmail** - Notify moderators
3. **Do both** - Combine comment and modmail actions

This bot combines the functionality of FlairTimerComment and FlairTimerModMail into a single unified interface.

---

## Features

- Configurable subreddit and scan interval
- Multiple flair configurations with different actions for each
- Tracks posts in `config/posts.json` so it survives restarts
- Flexible actions per flair: comment only, modmail only, or both
- Optional post locking and sticky comments
- Can run as a Python script or in Docker
- **One Action Per Flair Tenure**: Each post is actioned once per flair lifetime
  - Short-timer flairs (e.g., 0.01 hours) won't spam multiple actions
  - If moderator changes the flair and changes it back, post can be actioned again
- **Dynamic Config Reloading**: Moderators can reload wiki config via modmail command (no restart needed)
  - Send a modmail containing "reload-flairtimers" to reload the configuration
  - Bot automatically verifies sender is a moderator
  - Receives confirmation reply with status
  - Old messages are not reprocessed on restart (prevents spam)
- **Optimized for Rate Limiting**: Minimal API requests
  - Scans new posts only once per cycle (regardless of flair configs)
  - Caches submissions to check against all flairs without re-fetching
  - Eliminates redundant flair checks
  - ~60% reduction in Reddit API calls compared to earlier versions

---

## Configuration

Configuration is set up through two files:

### config/config.py

Base bot configuration:

```python
username = ""          # Reddit account used by the bot
password = ""          # account password
client_id = ""         # API credentials from https://www.reddit.com/prefs/apps
client_secret = ""     #
user_agent = "Flair Timer Mod Bot"

subreddit = ""         # e.g. "INEEEEDIT" or "All"
interval = 30          # seconds between subreddit scans
searchlimit = 600      # how many recent posts to examine (max 1000)
```

### Flair Timer Configuration (Wiki or File)

**Recommended: Load from Subreddit Wiki (Default)**

By default, flair timer configurations are loaded from a subreddit wiki page in YAML format. This allows you to update the bot's behavior without restarting:

1. Create a wiki page (e.g., `https://reddit.com/r/yoursubreddit/wiki/flair-timers`)
2. Add your flair timer configs in YAML format (see [WIKI_PAGE_EXAMPLE.md](WIKI_PAGE_EXAMPLE.md))
3. Set environment variables:
   - `FTMB_USE_WIKI_CONFIG=true` (default)
   - `FTMB_WIKI_PAGE=flair-timers` (customize as needed)

**Example Wiki Page Content (YAML):**

```yaml
- flair_text: "Waiting for OP"
  hours: 48
  action: "comment"
  comment_message: "This post has had the 'Waiting for OP' flair for 48 hours."
  messagetitle: "Modmail Notification"
  lock_post: false
  distinguish_sticky: false

- flair_text: "WFOP"
  hours: 0.0001
  action: "modmail"
  messagetitle: "Possible Abandoned Post"
  lock_post: false
  distinguish_sticky: false
```

**Fallback: Local File Configuration**

If wiki loading is disabled (`FTMB_USE_WIKI_CONFIG=false`) or fails, the bot uses `config/flairconfig.py`:

```python
flair_times = [
    {
        "flair_text": "Waiting for OP",           # Flair to watch for (case sensitive)
        "hours": 48,                              # How long flair must remain
        "action": "comment",                      # "comment", "modmail", or "both"
        "comment_message": "...",                 # Message to post as comment
        "messagetitle": "Modmail Notification",   # Modmail subject
        "lock_post": False,                       # Lock after comment?
        "distinguish_sticky": False               # Sticky the comment?
    },
]
```

#### Action Types

- **"comment"** - Posts a comment on the submission
- **"modmail"** - Sends a modmail to the subreddit
- **"both"** - Posts a comment AND sends modmail

#### Example Configurations

**Comment with sticky:**
```python
{
    "flair_text": "Waiting for OP",
    "hours": 48,
    "action": "comment",
    "comment_message": "OP hasn't responded in 48 hours!",
    "lock_post": False,
    "distinguish_sticky": True
}
```

**Modmail only:**
```python
{
    "flair_text": "Under Review",
    "hours": 24,
    "action": "modmail",
    "messagetitle": "Review Needed",
}
```

**Both comment and modmail:**
```python
{
    "flair_text": "Flagged",
    "hours": 12,
    "action": "both",
    "comment_message": "This has been flagged for 12 hours.",
    "messagetitle": "Flagged Post Alert",
    "lock_post": False,
    "distinguish_sticky": False
}
```

---

## Running the Bot

### Setup Requirements

1. **Create a subreddit wiki page** for flair timer configs (recommended):
   - Navigate to `https://reddit.com/r/yoursubreddit/wiki/`
   - Create a new page named `flair-timers` (or customize with `FTMB_WIKI_PAGE` env var)
   - Add your flair configurations in YAML format (see [WIKI_PAGE_EXAMPLE.md](WIKI_PAGE_EXAMPLE.md))
   - Give the bot account wiki permissions

2. **Fill in credentials** in `.env` or environment variables

### As a Python Script

1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python flairtimermodbot.py`

### In Docker

1. Fill in `.env` with your Reddit credentials and wiki page settings
2. Run: `docker-compose up -d`

### Environment Variables

```bash
# Reddit Credentials (required)
export FTMB_USERNAME=your_username
export FTMB_PASSWORD=your_password
export FTMB_CLIENT_ID=your_client_id
export FTMB_CLIENT_SECRET=your_client_secret
export FTMB_USER_AGENT="Flair Timer Mod Bot"

# Subreddit Configuration (required)
export FTMB_SUBREDDIT=your_subreddit

# Bot Polling (optional)
export FTMB_INTERVAL=30
export FTMB_SEARCHLIMIT=600

# Wiki Configuration (optional, recommended)
export FTMB_USE_WIKI_CONFIG=true        # Load configs from wiki (default)
export FTMB_WIKI_PAGE=flair-timers      # Wiki page name (default)
```

### Disabling Wiki Configuration

If you prefer to use the local `config/flairconfig.py` instead:

```bash
export FTMB_USE_WIKI_CONFIG=false
```

---

## Dynamic Config Reload (via Modmail)

Moderators can reload the flair timer configurations from the wiki without restarting the bot:

1. Send a modmail to the subreddit containing the text `reload-flairtimers`
2. The bot will verify you are a moderator
3. The bot will reload the wiki configuration
4. The bot will reply with a confirmation message

Example:
- Send modmail to `/r/yoursubreddit` with body: `reload-flairtimers`
- Bot replies: `✅ Successfully reloaded flair timer configs from wiki. Loaded 5 configurations.`

---

## One Action Per Flair Tenure

The bot ensures each post is actioned only once while it has a particular flair:

- **Post A** gets "Pending" flair (0.01 hour timer)
- **36 seconds later**: Bot actions it (sends modmail/comment)
- **30 seconds later, next cycle**: Bot scans and sees "Pending" still set
- **Bot skips it**: Post is marked as "processed" for "Pending" flair, won't action again
- **Moderator changes flair**: Bot removes it from "processed" list
- **If flair is set back to "Pending"**: Post can be actioned again

This prevents spam for short-timer flairs while allowing re-processing if moderators intentionally change and reapply a flair.

---

## Data Persistence

The bot stores tracked posts in `config/posts.json` with the structure:

```json
{
  "Waiting for OP": {
    "abc123": 1609459200.0,
    "def456": 1609545600.0
  },
  "Under Review": {
    "ghi789": 1609632000.0
  }
}
```

This allows the bot to survive restarts without losing track of which posts it's monitoring.

---

## Troubleshooting

- **Posts not being detected**: Check that `searchlimit` is high enough and the flair text matches exactly (case-sensitive)
- **Comments not posting**: Ensure bot has the required permissions in the subreddit
- **Modmail not sending**: Verify the bot has modmail permissions
- **Posts being unflaired**: The bot removes posts from tracking if they lose their flair

---

## Requirements

- Python 3.7+
- praw (Reddit API wrapper)

---

## License

See LICENSE file for details.
