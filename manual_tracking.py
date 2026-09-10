import re


def extract_post_ids(text):
    """Extract Reddit-style post IDs from modmail text.

    Manual tracking should only trigger when the message explicitly contains a
    tracking command and at least one valid post ID.
    """
    if not text:
        return []

    normalized = text.strip().lower()
    if not normalized:
        return []

    command_keywords = ["track-post", "track post", "manual-track"]
    has_command = any(keyword in normalized for keyword in command_keywords)

    if not has_command:
        return []

    parts = re.split(r"\s+", normalized)
    ids = [part for part in parts if re.fullmatch(r"[a-z0-9]{3,10}", part)]
    return ids


def apply_manual_tracking(reddit, post_ids, flair_times, all_posts):
    """Track submitted posts when they already have a configured flair.

    Returns a tuple of (tracked_ids, skipped_ids).
    """
    tracked_ids = []
    skipped_ids = []

    for submission_id in post_ids:
        try:
            submission = reddit.submission(submission_id)
        except Exception:
            skipped_ids.append(submission_id)
            continue

        current_flair = getattr(submission, "link_flair_text", None)
        matched_flair = None

        for flair_cfg in flair_times:
            flair_text = flair_cfg.get("flair_text")
            if current_flair == flair_text:
                matched_flair = flair_text
                break

        if not matched_flair:
            skipped_ids.append(submission_id)
            continue

        flair_bucket = all_posts.setdefault(matched_flair, {"tracking": {}, "processed": []})
        tracking = flair_bucket.setdefault("tracking", {})
        if submission_id not in tracking:
            tracking[submission_id] = 0
        tracked_ids.append(submission_id)

    return tracked_ids, skipped_ids
