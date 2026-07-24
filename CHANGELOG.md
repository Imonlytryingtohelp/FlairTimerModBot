# Changelog - FlairTimerModBot

All notable changes to this project will be documented in this file.

## [1.8.0] - 2026-07-24

### Added
- **Manual Post Tracking via Modmail**: Moderators can now trigger tracking by sending a modmail with one or more post IDs
  - Supports single post IDs or multiple IDs in one message
  - Example format: `track-post 1uvtrew` or `track-post 1uvtrew abc123 def456`
  - If a supplied post currently has a configured flair, the bot starts tracking it immediately
  - The bot replies to the modmail to confirm which posts were tracked and which could not be tracked



## [1.7.0] - 2026-03-18

### Added
- **Web Dashboard**: Added a simple Flask-based web GUI for viewing tracked and processed posts
  - Live table of stored posts from `config/posts.json`
  - Shows tracking start time, trigger time, and time remaining per post
  - Direct links to Reddit posts by post ID
  - Summary cards for tracking/processed/overdue/active flair totals
  - Auto-refresh with countdown and manual refresh button

- **Filtering & Search**: Added interactive dashboard filters
  - Filter by flair
  - Filter by status (tracking/processed)
  - Search by post ID substring
  - Sortable table columns
  - Filter selections now persist across page refreshes (flair, status, and post ID search)

- **Dockerized Web Service**: Added dedicated webapp container support
  - New `Dockerfile.webapp`
  - New `webapp` service in `docker-compose.yml`
  - Configurable dashboard port via `FTMB_WEB_PORT`

- **Live Flair Config Cache**: Dashboard now uses the exact active flair timer config from the bot
  - Bot writes `config/flair_times_cache.json` at startup and on successful wiki reload
  - Dashboard reads cache first, then falls back to `flairconfig.py` only if cache is unavailable

### Fixed
- **Dashboard/API Resilience**: Improved refresh behavior and transient failure handling
  - Added one automatic retry for API refresh calls
  - Keeps last successful data visible on intermittent refresh failure
  - Improved status messaging for stale vs fresh data states

- **Webapp Port Mapping**: Fixed compose port mapping mismatch that could cause empty HTTP responses

- **Dashboard Error Banner Visibility**: Fixed persistent red error banner caused by conflicting CSS display behavior

### Technical Details
- New files: `webapp.py`, `templates/dashboard.html`, `Dockerfile.webapp`
- Updated files: `docker-compose.yml`, `requirements.txt`, `flairtimermodbot.py`, `.env`
- New env var: `FTMB_WEB_PORT` (replaces `WEBAPP_PORT`)

## [1.6.1] - 2026-03-13

### Fixed
- **Chat Watcher Replay on Restart**: Messages are no longer reprocessed after bot restart
  - Captures bot startup timestamp when bot starts
  - Only processes messages created AFTER the bot started
  - Prevents spam of old reload commands when bot restarts
  - Uses message `created_utc` timestamp for comparison

### Technical Details
- `chat_message_watcher()` now accepts `startup_timestamp` parameter
- Checks `message.created_utc < startup_timestamp` and skips old messages
- Startup timestamp logged for debugging purposes
- No impact on legitimate new reload commands

---

## [1.6.0] - 2026-03-13

### Changed
- **One-Action-Per-Flair-Tenure**: Posts are now actioned only once per flair lifetime
  - New posts.json structure with "tracking" and "processed" lists per flair
  - Prevents duplicate actions on posts with short timers that don't change flair
  - Tracks which posts have been actioned and skips them on subsequent cycles
  - Removes posts from "processed" list if flair actually changes, allowing re-action if set back
  - Automatic migration of old posts.json format to new structure on startup

### Fixed
- **Spam of Short-Timer Flairs**: Posts with 0.01 hour timers no longer get spammed with multiple actions
  - Action fires once when timer expires
  - Post is marked as "processed"
  - If flair is manually changed by moderator, post is removed from processed list
  - If moderator sets flair back to original, post can be actioned again

### Technical Details
- posts.json structure changed: `{flair: {tracking: {...}, processed: [...]}}` (was flat dict)
- Migration code automatically converts old format to new format on load
- "Processed" list tracks which posts have been actioned to prevent re-processing
- Removed redundant "save post" logic - cleaner approach using processed tracking

---

## [1.5.3] - 2026-03-13

### Fixed
- **Modmail Rate Limiting (Reddit API Exception)**: Now properly handles RATELIMIT exceptions
  - Parses wait time from Reddit's RATELIMIT error message (e.g., "Take a break for 126 seconds")
  - Extracts numeric wait time with regex and respects it
  - Increased delay between modmail sends from 5s to 10s
  - Prevents rapid-fire modmail spam that triggers rate limits
  - Handles both 429 status codes AND RATELIMIT error exceptions

### Technical Details
- Updated error handling to catch Exception and check for "RATELIMIT" in message
- Uses regex to extract wait time: `(\d+)\s+seconds?`
- Modmail sends now have 10s spacing between them (was 5s)
- Graceful fallback to 5s, 10s, 20s, 60s if wait time can't be parsed

---

## [1.5.2] - 2026-03-13

### Fixed
- **Modmail Rate Limiting (Major)**: Now respects Reddit's `Retry-After` header
  - Parses the exact wait time Reddit specifies in 429 responses
  - Uses Reddit's recommended wait time (e.g., 186s) instead of guessing
  - Falls back to exponential backoff (5s, 10s, 20s, 60s) if header not provided
  - Properly handles large batches of modmails without triggering cascading rate limits

### Technical Details
- Checks HTTP response header `Retry-After` when rate limited
- Respects Redis's precise rate limit recovery time
- Minimizes failed attempts by following official guidance
- Better logging shows the actual wait time ordered by Reddit

---

## [1.5.1] - 2026-03-13

### Fixed
- **Modmail Rate Limiting**: Fixed 429 rate limit errors when sending multiple modmails
  - Added exponential backoff retry logic for rate limited modmail requests
  - Retry sequence with longer wait times: 5s, 10s, 20s, 60s
  - Up to 4 automatic retries for persistent rate limiting
  - Increased sleep time after modmail sends from 2s to 5s
  - Separate sleep times for comment-only vs modmail vs both actions
  - Better error logging for rate limit diagnostics

### Technical Details
- New `send_modmail_with_backoff()` function with retry logic
- Catches ResponseException with status code 429 and retries with configurable waits
- Logs rate limit warnings for monitoring
- Adaptive sleep times based on action type

---

## [1.5.0] - 2026-03-13

### Changed
- **Major API Optimization**: Significantly reduced Reddit API requests to prevent rate limiting
  - **Scan posts only once per cycle** instead of once per flair config (eliminates redundant scans)
  - **Submission caching** - cache submissions from one scan to check against all flair configs
  - **Eliminated duplicate flair checks** - old "posts_to_remove" logic removed (redundant with scan)
  - **Reduced post refreshes** - only refresh submissions when necessary for actions
  - **Shorter sleep times** - reduced post-action sleep from 5s to 2s (still safe)

### Performance Impact
- **~60% reduction in API calls** for typical usage (before: N flairs × M posts scanned; now: M posts scanned)
- **Maintains same response times** - posts are still detected and actioned at the same speed
- **Reduces rate limiting** - fewer concurrent requests per cycle

### Technical Details
- New submission cache prevents re-fetching same post multiple times
- Single scan loop replaced multiple per-flair-config loops
- Flair checks consolidated into single pass
- Error handling improved with try-catch blocks around all API calls

---

## [1.4.0] - 2026-03-13

### Added
- **Chat Message Watcher**: Monitor modmail/inbox for config reload commands
  - Moderators can send a message containing "reload-flairtimers" to reload wiki config
  - Bot verifies sender is a subreddit moderator before reloading
  - Sends confirmation reply to moderator with status
  - Runs as a background daemon thread without blocking main bot loop
  - Tracks processed messages to avoid duplicate processing
  - Allows dynamic config updates without restarting the bot

### Technical Details
- New function: `chat_message_watcher()` monitors Reddit inbox stream
- Processed message IDs tracked in `DB/chat_reload_requests.txt`
- Global `flair_times` variable updated when config is reloaded
- Integration with threading module for background execution

---

## [1.3.0] - 2026-03-13

### Added
- **Wiki-Based Configuration**: Load flair timer configs directly from subreddit wiki (YAML format)
  - Set `USE_WIKI_CONFIG=true` to enable (default)
  - Customize wiki page name via `WIKI_PAGE` environment variable (default: "flair-timers")
  - No more need to edit local config files
  - Changes to wiki page are reflected on next bot restart
  - Automatic fallback to `flairconfig.py` if wiki loading fails

- **PyYAML Dependency**: Added for parsing wiki-based YAML configurations

- **Example Documentation**: Created `WIKI_PAGE_EXAMPLE.md` with setup instructions and example YAML configurations

### Changed
- **Flair Timer Loading**: Now primarily loads from wiki instead of local files
- **Configuration Flow**: After authentication, bot loads wiki config; falls back to `flairconfig.py` if needed

### Technical Details
- Uses `reddit.subreddit().wiki[page_name].content_md` to fetch wiki content
- Graceful error handling with detailed error messages if wiki page not found
- Environment variables: `USE_WIKI_CONFIG`, `WIKI_PAGE`

---

## [1.2.0] - 2026-03-13

### Added
- **Update Checker Module**: Automatically checks for bot updates from upstream update server
  - Checks for updates every hour
  - Sends modmail notification to subreddit modteam when a new version is available
  - Includes 24-hour cooldown to prevent spam of multiple update notifications
  - Runs as a background daemon thread without blocking the main bot loop
  - Gracefully handles connection errors and timeouts

- **Easy Configuration**: Bot name and version now easily editable at the top of `flairtimermodbot.py`
  - `BOT_NAME` - Set to "FlairTimerModBot"
  - `BOT_VERSION` - Set to "1.2.0"

- **Requirements File**: Created `requirements.txt` for dependency management
  - praw >= 7.7.0 (Reddit API wrapper)
  - requests >= 2.31.0 (HTTP library for update checks)

### Changed
- **Main Bot Loop**: Now authenticates once at startup instead of re-authenticating on each cycle
  - Improves performance and reduces API overhead
  - Reuses existing Reddit session throughout bot runtime

- **Update Checker Integration**: Automatically started when bot runs
  - Integrates seamlessly without affecting existing bot functionality

### Technical Details
- Update server endpoint: `https://updts.slfhstd.uk/api/version/{bot_name}`
- Processed update checks tracked in `DB/.last_update_check.txt`
- Uses raw Reddit API `/api/compose/` endpoint for reliable modmail delivery
- Background thread created with daemon flag for clean shutdown

---

## [1.0.0] - Initial Release

### Features
- Monitors subreddit for posts with specific flairs
- Tracks posts with matched flairs and monitors time elapsed
- Supports configurable actions after timeout:
  - Post distinguished comments on the post
  - Send modmail notifications to subreddit modteam
  - Combined comment + modmail action
  - Optional post locking and sticky comments
- Configurable flair times via `config/flairconfig.py`
- Automatic configuration generation from environment variables
- Persistent post tracking via JSON storage
- Debug logging for monitoring and troubleshooting
