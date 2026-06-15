# MCP Twitter Server

A Model Context Protocol server for Twitter/X automation, search, timelines,
social graph operations, lists, notifications, direct messages, analytics, and
media downloads.

The server uses [xkit-py](https://github.com/inorilzy/xkit-py), a maintained
cookie-based Twitter/X web client that does not require the paid official API.

## Installation

```json
{
  "mcpServers": {
    "twitter": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/inorilzy/mcp-twitter-server",
        "mcp-twitter-server"
      ],
      "env": {
        "TWITTER_USERNAME": "@example",
        "TWITTER_EMAIL": "me@example.com",
        "TWITTER_PASSWORD": "secret"
      }
    }
  }
}
```

Optional:

```json
{
  "USER_AGENT": "Mozilla/5.0 ..."
}
```

Cookies are stored at `~/.mcp-twitter-server/cookies.json` after the first
successful login.

## Tools

### Read

- `search_twitter` - search posts by query, sorted by Top or Latest
- `get_user_tweets` - fetch posts from a user timeline
- `get_user_mentions` - find posts mentioning a user
- `get_timeline` - read the For You timeline
- `get_latest_timeline` - read the Following timeline
- `get_tweet_replies` - fetch replies for a post
- `get_full_thread` - reconstruct a thread around a post
- `get_conversation_tree` - render nested replies
- `get_similar_tweets` - fetch similar posts
- `get_user_highlights` - read user highlights
- `get_bookmarks` - read bookmarked posts

### Write

- `post_tweet` - publish a post, optionally with media, reply target, or mentions
- `delete_tweet` - delete a post
- `create_poll_tweet` - publish a poll
- `vote_on_poll` - vote on a poll
- `download_tweet_media` - download images or videos from a post

### Engagement

- `like_tweet` / `unlike_tweet`
- `retweet` / `unretweet`
- `bookmark_tweet` / `delete_bookmark`

### Social Graph

- `follow_user` / `unfollow_user`
- `block_user` / `unblock_user`
- `mute_user` / `unmute_user`
- `get_user_profile`
- `get_user_followers`
- `get_user_following`
- `get_user_verified_followers`
- `search_users`
- `bulk_user_lookup`
- `get_retweeters`
- `get_favoriters`

### Discovery

- `get_trends`
- `track_hashtag`
- `analyze_user_engagement`

### Lists

- `create_list`
- `get_my_lists`
- `get_list_tweets`
- `get_list_members`
- `add_user_to_list`
- `remove_user_from_list`

### Notifications

- `get_notifications`

### Direct Messages

- `send_dm`
- `delete_dm`
- `get_dm_history`
- `add_dm_reaction`
- `remove_dm_reaction`

### Streaming

- `stream_tweet_engagement`

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
mcp-twitter-server
```

Required environment variables:

```powershell
$env:TWITTER_USERNAME='@example'
$env:TWITTER_EMAIL='me@example.com'
$env:TWITTER_PASSWORD='secret'
```

## Notes

Twitter/X frequently changes private web API response shapes. This server keeps
MCP-facing behavior defensive and delegates low-level protocol maintenance to
`xkit-py`.
