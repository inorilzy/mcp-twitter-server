from fastmcp import FastMCP, Context
import xkit
import os
from pathlib import Path
import logging
from typing import Optional, List
import time

mcp = FastMCP("mcp-twitter-server")
logger = logging.getLogger(__name__)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

USERNAME = os.getenv('TWITTER_USERNAME')
EMAIL = os.getenv('TWITTER_EMAIL')
PASSWORD = os.getenv('TWITTER_PASSWORD')
USER_AGENT = os.getenv('USER_AGENT')
COOKIES_PATH = Path.home() / '.mcp-twitter-server' / 'cookies.json'
LIST_REMOVE_MEMBER_URL = (
    'https://x.com/i/api/graphql/cvDFkG5WjcXV0Qw5nfe1qQ/ListRemoveMember'
)

# Rate limit tracking
RATE_LIMITS = {}
RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes in seconds

async def get_twitter_client() -> xkit.Client:
    """Initialize and return an authenticated Twitter client."""
    client = xkit.Client('en-US', user_agent=USER_AGENT)

    if COOKIES_PATH.exists():
        client.load_cookies(COOKIES_PATH)
    else:
        try:
            await client.login(
                auth_info_1=USERNAME,
                auth_info_2=EMAIL,
                password=PASSWORD
            )
        except Exception as e:
            logger.error(f"Failed to login: {e}", exc_info=True)
            raise
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        client.save_cookies(COOKIES_PATH)

    return client

def check_rate_limit(endpoint: str) -> bool:
    """Check if we're within rate limits for a given endpoint."""
    now = time.time()
    if endpoint not in RATE_LIMITS:
        RATE_LIMITS[endpoint] = []

    # Remove old timestamps
    RATE_LIMITS[endpoint] = [t for t in RATE_LIMITS[endpoint] if now - t < RATE_LIMIT_WINDOW]

    # Check limits based on endpoint
    if endpoint == 'tweet':
        return len(RATE_LIMITS[endpoint]) < 300  # 300 tweets per 15 minutes
    elif endpoint == 'dm':
        return len(RATE_LIMITS[endpoint]) < 1000  # 1000 DMs per 15 minutes
    return True

# Existing search and read tools
@mcp.tool()
async def search_twitter(query: str, sort_by: str = 'Top', count: int = 10, ctx: Context = None) -> str:
    """Search twitter with a query. Sort by 'Top' or 'Latest'"""
    try:
        client = await get_twitter_client()
        tweets = await client.search_tweet(query, product=sort_by, count=count)
        return convert_tweets_to_markdown(tweets)
    except Exception as e:
        logger.error(f"Failed to search tweets: {e}", exc_info=True)
        return f"Failed to search tweets: {type(e).__name__}: {e}"

@mcp.tool()
async def get_user_tweets(username: str, tweet_type: str = 'Tweets', count: int = 10, ctx: Context = None) -> str:
    """Get tweets from a specific user's timeline."""
    try:
        client = await get_twitter_client()
        username = username.lstrip('@')
        user = await client.get_user_by_screen_name(username)
        if not user:
            return f"Could not find user {username}"

        tweets = await client.get_user_tweets(
            user_id=user.id,
            tweet_type=tweet_type,
            count=count
        )
        return convert_tweets_to_markdown(tweets)
    except Exception as e:
        logger.error(f"Failed to get user tweets: {e}", exc_info=True)
        return f"Failed to get user tweets: {type(e).__name__}: {e}"

@mcp.tool()
async def get_timeline(count: int = 20) -> str:
    """Get tweets from your home timeline (For You)."""
    try:
        client = await get_twitter_client()
        tweets = await client.get_timeline(count=count)
        return convert_tweets_to_markdown(tweets)
    except Exception as e:
        logger.error(f"Failed to get timeline: {e}", exc_info=True)
        return f"Failed to get timeline: {type(e).__name__}: {e}"

@mcp.tool()
async def get_latest_timeline(count: int = 20) -> str:
    """Get tweets from your home timeline (Following)."""
    try:
        client = await get_twitter_client()
        tweets = await client.get_latest_timeline(count=count)
        return convert_tweets_to_markdown(tweets)
    except Exception as e:
        logger.error(f"Failed to get latest timeline: {e}", exc_info=True)
        return f"Failed to get latest timeline: {type(e).__name__}: {e}"

# New write tools
@mcp.tool()
async def post_tweet(
    text: str,
    media_paths: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> str:
    """Post a tweet with optional media, reply, and tags."""
    try:
        if not check_rate_limit('tweet'):
            return "Rate limit exceeded for tweets. Please wait before posting again."

        client = await get_twitter_client()

        # Handle tags by converting to mentions
        if tags:
            mentions = ' '.join(f"@{tag.lstrip('@')}" for tag in tags)
            text = f"""{text}
{mentions}"""

        # Upload media if provided
        media_ids = []
        if media_paths:
            for path in media_paths:
                media_id = await client.upload_media(path, wait_for_completion=True)
                media_ids.append(media_id)

        # Create the tweet
        tweet = await client.create_tweet(
            text=text,
            media_ids=media_ids if media_ids else None,
            reply_to=reply_to
        )
        RATE_LIMITS.setdefault('tweet', []).append(time.time())
        return f"Successfully posted tweet: {tweet.id}"
    except Exception as e:
        logger.error(f"Failed to post tweet: {e}", exc_info=True)
        return f"Failed to post tweet: {type(e).__name__}: {e}"

@mcp.tool()
async def delete_tweet(tweet_id: str) -> str:
    """Delete a tweet by its ID."""
    try:
        client = await get_twitter_client()
        await client.delete_tweet(tweet_id)
        return f"Successfully deleted tweet {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to delete tweet: {e}", exc_info=True)
        return f"Failed to delete tweet: {type(e).__name__}: {e}"

@mcp.tool()
async def send_dm(user_id: str, message: str, media_path: Optional[str] = None) -> str:
    """Send a direct message to a user."""
    try:
        if not check_rate_limit('dm'):
            return "Rate limit exceeded for DMs. Please wait before sending again."

        client = await get_twitter_client()

        media_id = None
        if media_path:
            media_id = await client.upload_media(media_path, wait_for_completion=True)

        await client.send_dm(
            user_id=user_id,
            text=message,
            media_id=media_id
        )
        RATE_LIMITS.setdefault('dm', []).append(time.time())
        return f"Successfully sent DM to user {user_id}"
    except Exception as e:
        logger.error(f"Failed to send DM: {e}", exc_info=True)
        return f"Failed to send DM: {type(e).__name__}: {e}"

@mcp.tool()
async def delete_dm(message_id: str) -> str:
    """Delete a direct message by its ID."""
    try:
        client = await get_twitter_client()
        await client.delete_dm(message_id)
        return f"Successfully deleted DM {message_id}"
    except Exception as e:
        logger.error(f"Failed to delete DM: {e}", exc_info=True)
        return f"Failed to delete DM: {type(e).__name__}: {e}"

@mcp.tool()
async def get_tweet_replies(tweet_id: str, count: int = 20) -> str:
    """Get replies (comments) for a specific tweet by its ID."""
    try:
        client = await get_twitter_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if tweet is None:
            return f"Tweet {tweet_id} not found."

        replies = list(tweet.replies)[:count]
        if not replies:
            return f"No replies found for tweet {tweet_id}."

        result = [f"## Replies to tweet {tweet_id} by @{tweet.user.screen_name}", ""]
        result.append(f"> {tweet.text}")
        result.append(f"\n**{len(replies)} replies:**\n")

        for reply_thread in replies:
            # Each item in replies is a tweet whose .replies are sub-replies in that thread
            result.append(f"### @{reply_thread.user.screen_name}")
            result.append(f"**{reply_thread.created_at}**")
            result.append(reply_thread.text)
            # Include nested replies in the same thread if available
            if hasattr(reply_thread, 'replies') and reply_thread.replies:
                for sub in reply_thread.replies:
                    result.append(f"  - **@{sub.user.screen_name}**: {sub.text[:120]}")
            result.append("---")

        return "\n".join(result)
    except Exception as e:
        logger.error(f"Failed to get tweet replies: {e}", exc_info=True)
        return f"Failed to get tweet replies: {type(e).__name__}: {e}"

# ============================================================
# Helpers
# ============================================================

async def _resolve_user(client: xkit.Client, identifier: str):
    """Resolve a username (@handle) or numeric user_id to a User object."""
    identifier = identifier.lstrip('@')
    if identifier.isdigit():
        return await client.get_user_by_id(identifier)
    return await client.get_user_by_screen_name(identifier)


def _find_dict(obj, key: str, find_one: bool = True):
    """Return dict values for key from nested dict/list payloads."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            if key in value:
                found.append(value[key])
                if find_one:
                    return True
            for child in value.values():
                if walk(child) and find_one:
                    return True
        elif isinstance(value, list):
            for child in value:
                if walk(child) and find_one:
                    return True
        return False

    walk(obj)
    return found


def convert_users_to_markdown(users, header: Optional[str] = None) -> str:
    """Convert a list of users to compact markdown."""
    result = []
    if header:
        result.append(f"## {header}")
        result.append("")
    for u in users:
        verified = " ✅" if getattr(u, 'verified', False) or getattr(u, 'is_blue_verified', False) else ""
        protected = " 🔒" if getattr(u, 'protected', False) else ""
        result.append(f"### @{u.screen_name} — {u.name}{verified}{protected}")
        result.append(f"**ID:** `{u.id}`  |  👥 {getattr(u, 'followers_count', 0)} followers  |  📤 {getattr(u, 'following_count', 0)} following  |  📝 {getattr(u, 'statuses_count', 0)} tweets")
        desc = getattr(u, 'description', None)
        if desc:
            result.append(f"> {desc}")
        loc = getattr(u, 'location', None)
        if loc:
            result.append(f"📍 {loc}")
        result.append("---")
    return "\n".join(result) if result else "(no users)"


def convert_tweets_to_markdown(tweets) -> str:
    """Convert a list of tweets to markdown format."""
    result = []
    for tweet in tweets:
        user = tweet.user
        result.append(f"### @{user.screen_name} ({user.name})")
        result.append(f"**ID:** `{tweet.id}`  |  **Time:** {tweet.created_at}")
        result.append("")
        result.append(tweet.full_text or tweet.text)
        result.append("")
        # Engagement stats
        stats = []
        if tweet.view_count is not None:
            stats.append(f"👁 {tweet.view_count}")
        stats.append(f"❤️ {tweet.favorite_count}")
        stats.append(f"🔁 {tweet.retweet_count}")
        stats.append(f"💬 {tweet.reply_count}")
        stats.append(f"📌 {tweet.quote_count}")
        if tweet.bookmark_count:
            stats.append(f"🔖 {tweet.bookmark_count}")
        result.append("  ".join(stats))
        # URLs (may be list of dicts in newer API)
        if tweet.urls:
            url_strs = []
            for u in tweet.urls:
                if isinstance(u, dict):
                    url_strs.append(u.get('expanded_url') or u.get('url') or str(u))
                else:
                    url_strs.append(str(u))
            if url_strs:
                result.append("**Links:** " + " | ".join(url_strs))
        # Media (may be list of dicts or objects)
        if tweet.media:
            for media in tweet.media:
                if isinstance(media, dict):
                    murl = media.get('media_url_https') or media.get('media_url') or media.get('url')
                else:
                    murl = getattr(media, 'url', None) or getattr(media, 'media_url_https', None)
                if murl:
                    result.append(f"![media]({murl})")
        result.append("---")
    return "\n".join(result)


# ============================================================
# Tier 1: Engagement (like / retweet / bookmark)
# ============================================================

@mcp.tool()
async def like_tweet(tweet_id: str) -> str:
    """Like (favorite) a tweet by its ID."""
    try:
        client = await get_twitter_client()
        await client.favorite_tweet(tweet_id)
        return f"Successfully liked tweet {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to like tweet: {e}", exc_info=True)
        return f"Failed to like tweet: {type(e).__name__}: {e}"


@mcp.tool()
async def unlike_tweet(tweet_id: str) -> str:
    """Unlike (unfavorite) a tweet by its ID."""
    try:
        client = await get_twitter_client()
        await client.unfavorite_tweet(tweet_id)
        return f"Successfully unliked tweet {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to unlike tweet: {e}", exc_info=True)
        return f"Failed to unlike tweet: {type(e).__name__}: {e}"


@mcp.tool()
async def retweet(tweet_id: str) -> str:
    """Retweet a tweet by its ID."""
    try:
        client = await get_twitter_client()
        await client.retweet(tweet_id)
        return f"Successfully retweeted {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to retweet: {e}", exc_info=True)
        return f"Failed to retweet: {type(e).__name__}: {e}"


@mcp.tool()
async def unretweet(tweet_id: str) -> str:
    """Undo a retweet by tweet ID."""
    try:
        client = await get_twitter_client()
        await client.delete_retweet(tweet_id)
        return f"Successfully unretweeted {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to unretweet: {e}", exc_info=True)
        return f"Failed to unretweet: {type(e).__name__}: {e}"


@mcp.tool()
async def bookmark_tweet(tweet_id: str, folder_id: Optional[str] = None) -> str:
    """Add a tweet to bookmarks. Optionally specify a bookmark folder ID."""
    try:
        client = await get_twitter_client()
        if folder_id:
            await client.bookmark_tweet(tweet_id, folder_id=folder_id)
        else:
            await client.bookmark_tweet(tweet_id)
        return f"Successfully bookmarked tweet {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to bookmark tweet: {e}", exc_info=True)
        return f"Failed to bookmark tweet: {type(e).__name__}: {e}"


@mcp.tool()
async def delete_bookmark(tweet_id: str) -> str:
    """Remove a tweet from bookmarks."""
    try:
        client = await get_twitter_client()
        await client.delete_bookmark(tweet_id)
        return f"Successfully removed bookmark for tweet {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to delete bookmark: {e}", exc_info=True)
        return f"Failed to delete bookmark: {type(e).__name__}: {e}"


@mcp.tool()
async def get_bookmarks(count: int = 20) -> str:
    """List your bookmarked tweets."""
    try:
        client = await get_twitter_client()
        tweets = await client.get_bookmarks(count=count)
        return convert_tweets_to_markdown(tweets) or "(no bookmarks)"
    except Exception as e:
        logger.error(f"Failed to get bookmarks: {e}", exc_info=True)
        return f"Failed to get bookmarks: {type(e).__name__}: {e}"


# ============================================================
# Tier 1: Social Graph (follow / block / mute)
# ============================================================

@mcp.tool()
async def follow_user(username: str) -> str:
    """Follow a user by @screen_name or numeric user_id."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.follow_user(user.id)
        return f"Successfully followed @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to follow user: {e}", exc_info=True)
        return f"Failed to follow user: {type(e).__name__}: {e}"


@mcp.tool()
async def unfollow_user(username: str) -> str:
    """Unfollow a user by @screen_name or numeric user_id."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.unfollow_user(user.id)
        return f"Successfully unfollowed @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to unfollow user: {e}", exc_info=True)
        return f"Failed to unfollow user: {type(e).__name__}: {e}"


@mcp.tool()
async def block_user(username: str) -> str:
    """Block a user by @screen_name or numeric user_id."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.v11.create_blocks(user.id)
        return f"Successfully blocked @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to block user: {e}", exc_info=True)
        return f"Failed to block user: {type(e).__name__}: {e}"


@mcp.tool()
async def unblock_user(username: str) -> str:
    """Unblock a user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.v11.destroy_blocks(user.id)
        return f"Successfully unblocked @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to unblock user: {e}", exc_info=True)
        return f"Failed to unblock user: {type(e).__name__}: {e}"


@mcp.tool()
async def mute_user(username: str) -> str:
    """Mute a user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        # The high-level mute helper parses the response as a user object, which
        # can fail on rate-limit/string responses. The side effect is enough here.
        # Call v11 directly: the side effect (mute) is what we care about.
        await client.v11.create_mutes(user.id)
        return f"Successfully muted @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to mute user: {e}", exc_info=True)
        return f"Failed to mute user: {type(e).__name__}: {e}"


@mcp.tool()
async def unmute_user(username: str) -> str:
    """Unmute a user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.v11.destroy_mutes(user.id)
        return f"Successfully unmuted @{user.screen_name}"
    except Exception as e:
        logger.error(f"Failed to unmute user: {e}", exc_info=True)
        return f"Failed to unmute user: {type(e).__name__}: {e}"


# ============================================================
# Tier 1: User Lookup & Search
# ============================================================

@mcp.tool()
async def get_user_profile(username: str) -> str:
    """Get a user's full profile by @screen_name or numeric user_id."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        return convert_users_to_markdown([user], header=f"Profile: @{user.screen_name}")
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}", exc_info=True)
        return f"Failed to get user profile: {type(e).__name__}: {e}"


@mcp.tool()
async def get_user_followers(username: str, count: int = 20) -> str:
    """Get a list of followers for a given user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        followers = await client.get_user_followers(user.id, count=count)
        return convert_users_to_markdown(followers, header=f"Followers of @{user.screen_name}")
    except Exception as e:
        logger.error(f"Failed to get followers: {e}", exc_info=True)
        return f"Failed to get followers: {type(e).__name__}: {e}"


@mcp.tool()
async def get_user_following(username: str, count: int = 20) -> str:
    """Get a list of users the given user is following."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        following = await client.get_user_following(user.id, count=count)
        return convert_users_to_markdown(following, header=f"Following list of @{user.screen_name}")
    except Exception as e:
        logger.error(f"Failed to get following list: {e}", exc_info=True)
        return f"Failed to get following list: {type(e).__name__}: {e}"


@mcp.tool()
async def get_user_verified_followers(username: str, count: int = 20) -> str:
    """Get verified (blue-check) followers for a given user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        followers = await client.get_user_verified_followers(user.id, count=count)
        return convert_users_to_markdown(followers, header=f"Verified followers of @{user.screen_name}")
    except Exception as e:
        logger.error(f"Failed to get verified followers: {e}", exc_info=True)
        return f"Failed to get verified followers: {type(e).__name__}: {e}"


@mcp.tool()
async def search_users(query: str, count: int = 20) -> str:
    """Search for users by keyword."""
    try:
        client = await get_twitter_client()
        users = await client.search_user(query, count=count)
        return convert_users_to_markdown(users, header=f"User search: {query}")
    except Exception as e:
        logger.error(f"Failed to search users: {e}", exc_info=True)
        return f"Failed to search users: {type(e).__name__}: {e}"


@mcp.tool()
async def bulk_user_lookup(usernames: List[str]) -> str:
    """Look up multiple users in one call. Accepts @screen_names or user_ids."""
    try:
        client = await get_twitter_client()
        users = []
        errors = []
        for name in usernames:
            try:
                u = await _resolve_user(client, name)
                if u:
                    users.append(u)
                else:
                    errors.append(f"- {name}: not found")
            except Exception as ex:
                errors.append(f"- {name}: {ex}")
        out = convert_users_to_markdown(users, header=f"Bulk lookup ({len(users)}/{len(usernames)})")
        if errors:
            out += "\n\n**Errors:**\n" + "\n".join(errors)
        return out
    except Exception as e:
        logger.error(f"Failed bulk user lookup: {e}", exc_info=True)
        return f"Failed bulk user lookup: {type(e).__name__}: {e}"


@mcp.tool()
async def get_user_highlights(username: str, count: int = 20) -> str:
    """Get highlighted tweets from a user's profile."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        tweets = await client.get_user_highlights_tweets(user.id, count=count)
        return convert_tweets_to_markdown(tweets) or "(no highlights)"
    except Exception as e:
        logger.error(f"Failed to get highlights: {e}", exc_info=True)
        return f"Failed to get highlights: {type(e).__name__}: {e}"


# ============================================================
# Tier 1: Trends & Discovery
# ============================================================

@mcp.tool()
async def get_trends(category: str = 'trending', count: int = 20) -> str:
    """Get trending topics on Twitter. category: 'trending' | 'for-you' | 'news' | 'sports' | 'entertainment'."""
    try:
        client = await get_twitter_client()
        trends = await client.get_trends(category, count=count)
        if not trends:
            return "(no trends)"
        lines = [f"## Trends ({category})", ""]
        for i, t in enumerate(trends, 1):
            name = getattr(t, 'name', str(t))
            volume = getattr(t, 'tweets_count', None) or getattr(t, 'tweet_volume', None)
            domain = getattr(t, 'domain_context', '')
            extra = f" — {volume} tweets" if volume else ""
            if domain:
                extra += f" ({domain})"
            lines.append(f"{i}. **{name}**{extra}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get trends: {e}", exc_info=True)
        return f"Failed to get trends: {type(e).__name__}: {e}"


@mcp.tool()
async def get_user_mentions(username: str, count: int = 20) -> str:
    """Get recent tweets mentioning a specific user."""
    try:
        client = await get_twitter_client()
        username = username.lstrip('@')
        tweets = await client.search_tweet(f"@{username}", product='Latest', count=count)
        return convert_tweets_to_markdown(tweets) or f"(no recent mentions of @{username})"
    except Exception as e:
        logger.error(f"Failed to get mentions: {e}", exc_info=True)
        return f"Failed to get mentions: {type(e).__name__}: {e}"


@mcp.tool()
async def get_retweeters(tweet_id: str, count: int = 20) -> str:
    """List users who retweeted a specific tweet."""
    try:
        client = await get_twitter_client()
        users = await client.get_retweeters(tweet_id, count=count)
        return convert_users_to_markdown(users, header=f"Retweeters of {tweet_id}")
    except Exception as e:
        logger.error(f"Failed to get retweeters: {e}", exc_info=True)
        return f"Failed to get retweeters: {type(e).__name__}: {e}"


@mcp.tool()
async def get_favoriters(tweet_id: str, count: int = 20) -> str:
    """List users who liked a specific tweet."""
    try:
        client = await get_twitter_client()
        users = await client.get_favoriters(tweet_id, count=count)
        return convert_users_to_markdown(users, header=f"Likers of {tweet_id}")
    except Exception as e:
        logger.error(f"Failed to get favoriters: {e}", exc_info=True)
        return f"Failed to get favoriters: {type(e).__name__}: {e}"


@mcp.tool()
async def get_similar_tweets(tweet_id: str) -> str:
    """Get tweets similar to a given tweet (Twitter's 'more like this' feature)."""
    try:
        client = await get_twitter_client()
        tweets = await client.get_similar_tweets(tweet_id)
        return convert_tweets_to_markdown(tweets) or "(no similar tweets)"
    except Exception as e:
        logger.error(f"Failed to get similar tweets: {e}", exc_info=True)
        return f"Failed to get similar tweets: {type(e).__name__}: {e}"


# ============================================================
# Tier 2: Polls
# ============================================================

@mcp.tool()
async def create_poll_tweet(text: str, choices: List[str], duration_minutes: int = 1440) -> str:
    """Create a tweet with a poll. choices: 2-4 options. duration_minutes: 5-10080 (default 1 day)."""
    try:
        if not (2 <= len(choices) <= 4):
            return "Poll requires 2-4 choices."
        client = await get_twitter_client()
        poll_uri = await client.create_poll(choices, duration_minutes)
        tweet = await client.create_tweet(text=text, poll_uri=poll_uri)
        if tweet is None:
            # X accepted the tweet but the client failed to parse the response.
            return "Poll tweet likely created (server accepted) but ID unavailable due to response parse error"
        return f"Successfully posted poll tweet: {tweet.id}"
    except Exception as e:
        logger.error(f"Failed to create poll: {e}", exc_info=True)
        return f"Failed to create poll: {type(e).__name__}: {e}"


@mcp.tool()
async def vote_on_poll(tweet_id: str, choice_label: str) -> str:
    """Vote on a poll. choice_label is the exact text of the option to select."""
    try:
        client = await get_twitter_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if tweet is None or not getattr(tweet, 'poll', None):
            return f"Tweet {tweet_id} has no poll."
        poll = tweet.poll
        # Poll.vote may raise KeyError parsing the response even though
        # the underlying HTTP request succeeded. Treat KeyError as success.
        try:
            await poll.vote(choice_label)
        except KeyError as ke:
            logger.warning(f"vote_on_poll: ignored parse error {ke}; vote likely accepted")
        return f"Vote recorded for '{choice_label}' on poll {tweet_id}"
    except Exception as e:
        logger.error(f"Failed to vote: {e}", exc_info=True)
        return f"Failed to vote: {type(e).__name__}: {e}"


# ============================================================
# Tier 2: Lists
# ============================================================

@mcp.tool()
async def create_list(name: str, description: str = '', is_private: bool = False) -> str:
    """Create a new Twitter list."""
    try:
        client = await get_twitter_client()
        lst = await client.create_list(name, description, is_private)
        return f"Successfully created list '{lst.name}' (ID: {lst.id})"
    except Exception as e:
        logger.error(f"Failed to create list: {e}", exc_info=True)
        return f"Failed to create list: {type(e).__name__}: {e}"


@mcp.tool()
async def get_my_lists() -> str:
    """Get all lists owned by the authenticated user."""
    try:
        client = await get_twitter_client()
        # The high-level list helper assumes one response shape.
        # which raises KeyError when X returns the new schema. Call the raw
        # gql endpoint and pull any nested 'list' dicts defensively.
        try:
            response, _ = await client.gql.list_management_pace_timeline(100, None)
        except AttributeError:
            lists = await client.get_lists()
            response = None
        if response is not None:
            raw_lists = _find_dict(response, 'list', find_one=False) or []
            lists = []
            for raw in raw_lists:
                if isinstance(raw, dict) and raw.get('id_str'):
                    try:
                        lists.append(xkit.List(client, raw))
                    except Exception:
                        continue
        if not lists:
            return "(no lists)"
        lines = ["## Your Lists", ""]
        for lst in lists:
            visibility = "🔒 private" if getattr(lst, 'is_private', False) else "🌐 public"
            lines.append(
                f"- **{getattr(lst, 'name', '?')}** (`{getattr(lst, 'id', '?')}`)"
                f" — {visibility} — {getattr(lst, 'member_count', 0)} members"
            )
            if getattr(lst, 'description', None):
                lines.append(f"  > {lst.description}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get lists: {e}", exc_info=True)
        return f"Failed to get lists: {type(e).__name__}: {e}"


@mcp.tool()
async def get_list_tweets(list_id: str, count: int = 20) -> str:
    """Get tweets from a Twitter list."""
    try:
        client = await get_twitter_client()
        tweets = await client.get_list_tweets(list_id, count=count)
        return convert_tweets_to_markdown(tweets) or "(no tweets)"
    except Exception as e:
        logger.error(f"Failed to get list tweets: {e}", exc_info=True)
        return f"Failed to get list tweets: {type(e).__name__}: {e}"


@mcp.tool()
async def get_list_members(list_id: str, count: int = 20) -> str:
    """Get members of a Twitter list."""
    try:
        client = await get_twitter_client()
        members = await client.get_list_members(list_id, count=count)
        return convert_users_to_markdown(members, header=f"Members of list {list_id}")
    except Exception as e:
        logger.error(f"Failed to get list members: {e}", exc_info=True)
        return f"Failed to get list members: {type(e).__name__}: {e}"


@mcp.tool()
async def add_user_to_list(list_id: str, username: str) -> str:
    """Add a user to one of your lists."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        await client.add_list_member(list_id, user.id)
        return f"Added @{user.screen_name} to list {list_id}"
    except Exception as e:
        logger.error(f"Failed to add list member: {e}", exc_info=True)
        return f"Failed to add list member: {type(e).__name__}: {e}"


@mcp.tool()
async def remove_user_from_list(list_id: str, username: str) -> str:
    """Remove a user from one of your lists."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        # The high-level remove helper sends feature flags that can cause a
        # server-side DecodeException; call the GQL endpoint directly
        # with an empty features dict to avoid the schema mismatch.
        variables = {'listId': list_id, 'userId': user.id}
        response, _ = await client.gql.gql_post(
            LIST_REMOVE_MEMBER_URL, variables, {}
        )
        if 'errors' in response:
            raise Exception(response['errors'][0]['message'])
        return f"Removed @{user.screen_name} from list {list_id}"
    except Exception as e:
        logger.error(f"Failed to remove list member: {e}", exc_info=True)
        return f"Failed to remove list member: {type(e).__name__}: {e}"


# ============================================================
# Tier 2: Notifications
# ============================================================

@mcp.tool()
async def get_notifications(notification_type: str = 'All', count: int = 20) -> str:
    """Get your notifications. type: 'All' | 'Verified' | 'Mentions'."""
    try:
        client = await get_twitter_client()
        # The high-level notification helper expects response['globalObjects'],
        # which X removed in 2026 — surfaces as 'NoneType' has no attribute 'get'.
        # Bypass: call v11 endpoint directly and pull notification text from
        # globalObjects if present, otherwise scan the timeline entries.
        ntype = (notification_type or 'All').capitalize()
        f = {
            'All': client.v11.notifications_all,
            'Verified': client.v11.notifications_verified,
            'Mentions': client.v11.notifications_mentions,
        }.get(ntype)
        if f is None:
            return f"Unknown notification_type '{notification_type}' (use All/Verified/Mentions)"
        response, _ = await f(count, None)
        lines = [f"## Notifications ({ntype})", ""]
        added = 0

        # Legacy path (globalObjects)
        global_objects = response.get('globalObjects') if isinstance(response, dict) else None
        if isinstance(global_objects, dict):
            users = global_objects.get('users') or {}
            tweets = global_objects.get('tweets') or {}
            notifs = global_objects.get('notifications') or {}
            for n in list(notifs.values())[:count]:
                msg = (n.get('message') or {}).get('text') or n.get('description') or ''
                tmpl = (n.get('template') or {}).get('aggregateUserActionsV1') or {}
                from_users = tmpl.get('fromUsers') or []
                who = ''
                if from_users:
                    uid = (from_users[0].get('user') or {}).get('id')
                    if uid and str(uid) in users:
                        who = '@' + users[str(uid)].get('screen_name', '')
                lines.append(f"- **{who}** {msg}".rstrip())
                target = tmpl.get('targetObjects') or []
                if target and 'tweet' in target[0]:
                    tid = str(target[0]['tweet'].get('id', ''))
                    if tid in tweets:
                        snippet = (tweets[tid].get('full_text') or tweets[tid].get('text') or '')[:160]
                        if snippet:
                            lines.append(f"  > {snippet}")
                added += 1

        # New schema fallback: walk entries for any timeline-tweet
        if added == 0:
            entries_list = _find_dict(response, 'entries', find_one=True)
            entries = entries_list[0] if entries_list else []
            for e in entries[:count]:
                ic = _find_dict(e, 'itemContent', find_one=True)
                if not ic:
                    continue
                tweet_results = _find_dict(ic[0], 'result', find_one=True)
                if not tweet_results:
                    continue
                legacy = (tweet_results[0].get('legacy') or {}) if isinstance(tweet_results[0], dict) else {}
                text = (legacy.get('full_text') or legacy.get('text') or '')[:200]
                core = (tweet_results[0].get('core') or {}) if isinstance(tweet_results[0], dict) else {}
                user_results = (core.get('user_results') or {}).get('result') or {}
                handle = ((user_results.get('core') or {}).get('screen_name')
                          or (user_results.get('legacy') or {}).get('screen_name')
                          or '?')
                lines.append(f"- **@{handle}** {text}")
                added += 1

        if added == 0:
            return "(no notifications)"
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get notifications: {e}", exc_info=True)
        return f"Failed to get notifications: {type(e).__name__}: {e}"


# ============================================================
# Tier 2: DM extras
# ============================================================

@mcp.tool()
async def get_dm_history(username: str, count: int = 20) -> str:
    """Get DM conversation history with a specific user."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        messages = await client.get_dm_history(user.id)
        msgs = list(messages)[:count]
        if not msgs:
            return f"(no DM history with @{user.screen_name})"
        lines = [f"## DM history with @{user.screen_name}", ""]
        for m in msgs:
            sender = getattr(m, 'sender_id', '?')
            text = getattr(m, 'text', '')
            ts = getattr(m, 'time', '') or getattr(m, 'created_at', '')
            lines.append(f"**{sender}** ({ts}): {text}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get DM history: {e}", exc_info=True)
        return f"Failed to get DM history: {type(e).__name__}: {e}"


@mcp.tool()
async def add_dm_reaction(conversation_id: str, message_id: str, emoji: str) -> str:
    """Add an emoji reaction to a DM message."""
    try:
        client = await get_twitter_client()
        await client.add_reaction_to_message(message_id, conversation_id, emoji)
        return f"Added reaction {emoji} to message {message_id}"
    except Exception as e:
        logger.error(f"Failed to add reaction: {e}", exc_info=True)
        return f"Failed to add reaction: {type(e).__name__}: {e}"


@mcp.tool()
async def remove_dm_reaction(conversation_id: str, message_id: str, emoji: str) -> str:
    """Remove an emoji reaction from a DM message."""
    try:
        client = await get_twitter_client()
        await client.remove_reaction_from_message(message_id, conversation_id, emoji)
        return f"Removed reaction {emoji} from message {message_id}"
    except Exception as e:
        logger.error(f"Failed to remove reaction: {e}", exc_info=True)
        return f"Failed to remove reaction: {type(e).__name__}: {e}"


# ============================================================
# Tier 3: Analytics & Higher-Level Tools
# ============================================================

@mcp.tool()
async def get_full_thread(tweet_id: str) -> str:
    """Reconstruct the full thread containing a tweet (root + all author follow-ups)."""
    try:
        client = await get_twitter_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet:
            return f"Tweet {tweet_id} not found."

        # Walk up to root by following in_reply_to chain
        chain = [tweet]
        current = tweet
        seen = {tweet.id}
        for _ in range(20):  # safety cap
            parent_id = getattr(current, 'in_reply_to', None)
            if not parent_id or parent_id in seen:
                break
            try:
                parent = await client.get_tweet_by_id(parent_id)
            except Exception:
                break
            if not parent:
                break
            chain.append(parent)
            seen.add(parent.id)
            current = parent
        chain.reverse()  # root first

        # Pull follow-ups by the same author from replies of root
        root = chain[0]
        author_id = root.user.id
        author_followups = []
        try:
            for r in list(root.replies)[:50]:
                if r.user.id == author_id and r.id not in seen:
                    author_followups.append(r)
                    seen.add(r.id)
        except Exception:
            pass

        result = [f"## Full thread (root: @{root.user.screen_name})", ""]
        for i, t in enumerate(chain + author_followups, 1):
            result.append(f"### {i}. @{t.user.screen_name} — `{t.id}`")
            result.append(t.full_text or t.text)
            result.append(f"❤️ {t.favorite_count}  🔁 {t.retweet_count}  💬 {t.reply_count}")
            result.append("---")
        return "\n".join(result)
    except Exception as e:
        logger.error(f"Failed to build thread: {e}", exc_info=True)
        return f"Failed to build thread: {type(e).__name__}: {e}"


@mcp.tool()
async def get_conversation_tree(tweet_id: str, max_replies: int = 30) -> str:
    """Get the reply tree structure for a tweet (root + nested replies)."""
    try:
        client = await get_twitter_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet:
            return f"Tweet {tweet_id} not found."

        lines = [f"## Conversation tree: {tweet_id}", ""]
        lines.append(f"**@{tweet.user.screen_name}**: {tweet.full_text or tweet.text}")
        lines.append(f"  ❤️ {tweet.favorite_count}  🔁 {tweet.retweet_count}  💬 {tweet.reply_count}")
        lines.append("")

        replies = list(tweet.replies)[:max_replies]
        for r in replies:
            lines.append(f"├─ **@{r.user.screen_name}** (`{r.id}`): {(r.full_text or r.text)[:200]}")
            lines.append(f"│   ❤️ {r.favorite_count}  🔁 {r.retweet_count}  💬 {r.reply_count}")
            if hasattr(r, 'replies') and r.replies:
                for sub in list(r.replies)[:5]:
                    lines.append(f"│   └─ @{sub.user.screen_name}: {(sub.full_text or sub.text)[:150]}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get conversation tree: {e}", exc_info=True)
        return f"Failed to get conversation tree: {type(e).__name__}: {e}"


@mcp.tool()
async def analyze_user_engagement(username: str, sample_size: int = 20) -> str:
    """Analyze a user's engagement rate based on their recent tweets."""
    try:
        client = await get_twitter_client()
        user = await _resolve_user(client, username)
        if not user:
            return f"Could not find user {username}"
        tweets = await client.get_user_tweets(user.id, tweet_type='Tweets', count=sample_size)
        tweet_list = list(tweets)
        if not tweet_list:
            return f"No tweets found for @{user.screen_name}"

        def _i(v):
            try:
                return int(v) if v is not None else 0
            except (TypeError, ValueError):
                return 0

        total_likes = sum(_i(t.favorite_count) for t in tweet_list)
        total_rts = sum(_i(t.retweet_count) for t in tweet_list)
        total_replies = sum(_i(t.reply_count) for t in tweet_list)
        total_views = sum(_i(t.view_count) for t in tweet_list)
        n = len(tweet_list)
        followers = getattr(user, 'followers_count', 0) or 1

        avg_likes = total_likes / n
        avg_rts = total_rts / n
        avg_replies = total_replies / n
        avg_views = total_views / n if total_views else 0
        engagement_per_follower = (avg_likes + avg_rts + avg_replies) / followers * 100

        # Find top tweet
        top = max(tweet_list, key=lambda t: _i(t.favorite_count) + _i(t.retweet_count) * 2)

        lines = [
            f"## Engagement analysis: @{user.screen_name}",
            "",
            f"**Sample:** {n} recent tweets",
            f"**Followers:** {followers:,}",
            "",
            f"- Avg likes/tweet:    {avg_likes:.1f}",
            f"- Avg retweets/tweet: {avg_rts:.1f}",
            f"- Avg replies/tweet:  {avg_replies:.1f}",
            f"- Avg views/tweet:    {avg_views:,.0f}" if avg_views else "- Avg views/tweet:    N/A",
            f"- Engagement rate:    {engagement_per_follower:.3f}% of followers per tweet",
            "",
            f"**Top tweet** (`{top.id}`):",
            f"> {(top.full_text or top.text)[:200]}",
            f"❤️ {_i(top.favorite_count)}  🔁 {_i(top.retweet_count)}  💬 {_i(top.reply_count)}",
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed engagement analysis: {e}", exc_info=True)
        return f"Failed engagement analysis: {type(e).__name__}: {e}"


@mcp.tool()
async def track_hashtag(hashtag: str, sample_size: int = 50) -> str:
    """Analyze recent activity on a hashtag (volume, top tweets, top authors)."""
    try:
        client = await get_twitter_client()
        tag = hashtag if hashtag.startswith('#') else f"#{hashtag}"
        tweets = await client.search_tweet(tag, product='Latest', count=sample_size)
        tweet_list = list(tweets)
        if not tweet_list:
            return f"No tweets found for {tag}"

        total_likes = sum(t.favorite_count for t in tweet_list)
        total_rts = sum(t.retweet_count for t in tweet_list)
        author_counts: dict = {}
        for t in tweet_list:
            author_counts[t.user.screen_name] = author_counts.get(t.user.screen_name, 0) + 1
        top_authors = sorted(author_counts.items(), key=lambda x: -x[1])[:5]
        top_tweets = sorted(tweet_list, key=lambda t: t.favorite_count + t.retweet_count * 2, reverse=True)[:3]

        lines = [
            f"## Hashtag report: {tag}",
            "",
            f"**Sample:** {len(tweet_list)} recent tweets",
            f"**Total likes:** {total_likes}  |  **Total retweets:** {total_rts}",
            "",
            "### Top authors",
        ]
        for name, c in top_authors:
            lines.append(f"- @{name}: {c} tweets")
        lines.extend(["", "### Top tweets"])
        for t in top_tweets:
            lines.append(f"- **@{t.user.screen_name}** (`{t.id}`): {(t.full_text or t.text)[:160]}")
            lines.append(f"  ❤️ {t.favorite_count}  🔁 {t.retweet_count}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed hashtag tracking: {e}", exc_info=True)
        return f"Failed hashtag tracking: {type(e).__name__}: {e}"


@mcp.tool()
async def download_tweet_media(tweet_id: str, output_dir: Optional[str] = None) -> str:
    """Download all media (images/videos) from a tweet to local disk."""
    try:
        import httpx
        client = await get_twitter_client()
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet:
            return f"Tweet {tweet_id} not found."
        if not tweet.media:
            return f"Tweet {tweet_id} has no media."

        out_dir = Path(output_dir) if output_dir else Path.home() / '.mcp-twitter-server' / 'media' / tweet_id
        out_dir.mkdir(parents=True, exist_ok=True)

        saved = []
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as http:
            for i, media in enumerate(tweet.media):
                # Prefer highest quality video, else image
                url = None
                ext = 'bin'
                video_info = getattr(media, 'video_info', None)
                if video_info and getattr(video_info, 'variants', None):
                    mp4s = [v for v in video_info.variants if getattr(v, 'content_type', '') == 'video/mp4']
                    if mp4s:
                        best = max(mp4s, key=lambda v: getattr(v, 'bitrate', 0) or 0)
                        url = best.url
                        ext = 'mp4'
                if not url:
                    url = getattr(media, 'media_url', None) or getattr(media, 'url', None)
                    if url:
                        ext = url.rsplit('.', 1)[-1].split('?')[0] or 'jpg'
                if not url:
                    continue
                resp = await http.get(url)
                resp.raise_for_status()
                fname = out_dir / f"media_{i}.{ext}"
                fname.write_bytes(resp.content)
                saved.append(str(fname))
        if not saved:
            return f"No downloadable media URLs found for tweet {tweet_id}"
        return f"Downloaded {len(saved)} files to {out_dir}:\n" + "\n".join(f"- {f}" for f in saved)
    except Exception as e:
        logger.error(f"Failed to download media: {e}", exc_info=True)
        return f"Failed to download media: {type(e).__name__}: {e}"


# ============================================================
# Tier 4: Streaming (experimental)
# ============================================================

@mcp.tool()
async def stream_tweet_engagement(tweet_id: str, duration_seconds: int = 30) -> str:
    """Subscribe to a tweet's engagement stream and report updates over `duration_seconds`."""
    try:
        import asyncio
        client = await get_twitter_client()
        topic = f"tweet_engagement_{tweet_id}"
        session = await client.get_streaming_session([topic])

        # already subscribed via constructor, but be defensive
        try:
            await session.subscribe_topics([topic])
        except Exception:
            pass

        events: List[str] = []
        deadline = time.time() + duration_seconds
        try:
            async for topic_name, payload in session:
                events.append(f"[{topic_name}] {payload}")
                if time.time() > deadline or len(events) > 200:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as inner:
            events.append(f"(stream ended: {inner})")
        finally:
            try:
                await session.unsubscribe_topics([topic])
            except Exception:
                pass

        if not events:
            return f"(no engagement events received in {duration_seconds}s for tweet {tweet_id})"
        return f"## Stream events for {tweet_id} ({len(events)})\n\n" + "\n".join(events[:100])
    except Exception as e:
        logger.error(f"Failed to stream engagement: {e}", exc_info=True)
        return f"Failed to stream engagement: {type(e).__name__}: {e}"
