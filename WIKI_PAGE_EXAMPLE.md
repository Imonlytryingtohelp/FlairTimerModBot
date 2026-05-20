# Example Wiki Page Format for Flair Timer Configs

Create a wiki page on your subreddit (e.g., `https://reddit.com/r/yoursubreddit/wiki/flair-timers`) with the following YAML format:

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
  comment_message: ""
  messagetitle: "Possible Abandoned Post"
  lock_post: false
  distinguish_sticky: false

- flair_text: "Solved"
  hours: 72
  action: "modmail"
  comment_message: ""
  messagetitle: "Solved Post Notification"
  lock_post: false
  distinguish_sticky: false

- flair_text: "Pending Review"
  hours: 24
  action: "both"
  comment_message: "This post has been pending review for 24 hours."
  messagetitle: "Review Pending Notification"
  lock_post: false
  distinguish_sticky: true
```

## Configuration Options

### Required Fields
- **flair_text**: The exact flair text to match on posts
- **hours**: Number of hours to wait before taking action
- **action**: Action to perform - `"comment"`, `"modmail"`, or `"both"`

### Optional Fields
- **comment_message**: Message to post as a comment (used if action is "comment" or "both")
- **messagetitle**: Subject line for modmail (used if action is "modmail" or "both")
- **lock_post**: `true` or `false` - Lock the post after taking action
- **distinguish_sticky**: `true` or `false` - Make the comment sticky (only applies to comments)

## Setup Instructions

1. **Enable Wiki for Your Subreddit** (if not already enabled)
   - Go to subreddit settings → Enable wiki → Save

2. **Create the Wiki Page**
   - Go to `https://reddit.com/r/yoursubreddit/wiki/`
   - Click "Create Page"
   - Name it `flair-timers` (or customize via `FTMB_WIKI_PAGE` environment variable)
   - Paste the YAML configuration above
   - Submit

3. **Set Bot Permissions**
   - Add the bot account as a moderator with wiki permissions
   - The bot needs permission to read the wiki page

4. **Configure Environment Variables**
   - Set `FTMB_USE_WIKI_CONFIG=true` in your `.env` file
   - Set `FTMB_WIKI_PAGE=flair-timers` (or your custom page name)

5. **Rebuild and Restart**
   ```bash
   docker-compose build --no-cache
   docker-compose restart
   ```

## Dynamic Config Reload

After the bot is set up, moderators can reload the configuration without restarting the bot:

1. Send a modmail to your subreddit with the text "reload-flairtimers"
2. The bot will check if you're a moderator
3. The bot will reload the wiki page
4. The bot will reply with a confirmation message

This allows you to test configuration changes quickly without restarting the container.

## Fallback

If the wiki page cannot be loaded, the bot will automatically fall back to using `config/flairconfig.py` if `FTMB_USE_WIKI_CONFIG=false` or if there's an error reading the wiki.
