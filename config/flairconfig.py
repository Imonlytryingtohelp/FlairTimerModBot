# flairconfig.py
# This file defines the list of flair time configs for the bot.
# Edit this file to customize flair behaviors.
#
# For each config:
# - "action": "comment" posts a comment, "modmail" sends modmail, "both" does both
# - "comment_message": Message to post (used if action is "comment" or "both")
# - "messagetitle": Title for modmail (used if action is "modmail" or "both")
# - "lock_post": Lock the submission after comment (only for comment action)
# - "distinguish_sticky": Sticky the comment (only for comment action)

flair_times = [
    {
        "flair_text": "Waiting for OP",
        "hours": 48,
        "action": "comment",
        "comment_message": "This post has had the 'Waiting for OP' flair for 48 hours.",
        "messagetitle": "Modmail Notification",
        "lock_post": False,
        "distinguish_sticky": False
    },

    {
        "flair_text": "WFOP",
        "hours": 0.0001,
        "action": "modmail",
        "comment_message": "Dummy comment",
        "messagetitle": "Possible Abandoned Post",
        "lock_post": False,
        "distinguish_sticky": False
    },

    {
        "flair_text": "Solved",
        "hours": 0.0001,
        "action": "modmail",
        "comment_message": "Dummy comment",
        "messagetitle": "Confirm Solved Post",
        "lock_post": False,
        "distinguish_sticky": False
    }
    # Example of modmail-only config:
    # {
    #     "flair_text": "Solved",
    #     "hours": 72,
    #     "action": "modmail",
    #     "comment_message": "",
    #     "messagetitle": "Solved Post Notification",
    #     "lock_post": False,
    #     "distinguish_sticky": False
    # },
    # Example of both comment and modmail:
    # {
    #     "flair_text": "Pending Review",
    #     "hours": 24,
    #     "action": "both",
    #     "comment_message": "This post has been pending review for 24 hours.",
    #     "messagetitle": "Review Pending Notification",
    #     "lock_post": False,
    #     "distinguish_sticky": True
    # },
]
