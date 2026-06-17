# MCP Twitter Server

A Model Context Protocol server for Twitter/X automation, search, timelines,
social graph operations, lists, notifications, direct messages, analytics, and
media downloads.

The server uses [xkit-py](https://github.com/inorilzy/xkit-py), a maintained
cookie-based Twitter/X web client that does not require the paid official API.

## What it is for

- Let MCP-compatible agents search, read, and operate Twitter/X through local credentials.
- Keep Twitter/X cookies on the user's machine instead of sending them to a hosted service.
- Expose a broad tool surface while delegating low-level Twitter/X web API maintenance to `xkit-py`.

It is not a password-login bot, hosted API proxy, or guarantee against Twitter/X rate limits and response changes.

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
        "TWITTER_COOKIES_PATH": "/absolute/path/to/x-cookies.json"
      }
    }
  }
}
```

Optional:

```json
{
  "USER_AGENT": "Mozilla/5.0 ...",
  "TWITTER_COOKIES_JSON": "{\"cookies\":[...]}"
}
```

The server does not perform password login. Log in to `x.com` in a browser,
export cookies, and provide them through `TWITTER_COOKIES_PATH` or
`TWITTER_COOKIES_JSON`. The cookies must include `auth_token` and `ct0`.

By default, the server reads:

```text
~/.mcp-twitter-server/cookies.json
```

## Configuration

| Name | Required | Description |
| --- | --- | --- |
| `TWITTER_COOKIES_PATH` | Recommended | Absolute path to exported Twitter/X cookies JSON. |
| `TWITTER_COOKIES_JSON` | Optional | Inline exported cookie JSON. Useful for temporary local runs. |
| `USER_AGENT` | Optional | Browser-like user agent override. |

Cookies must include `auth_token` and `ct0`.

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

Required cookie configuration:

```powershell
$env:TWITTER_COOKIES_PATH='C:\path\to\x-cookies.json'
```

Alternatively:

```powershell
$env:TWITTER_COOKIES_JSON='<exported-cookie-json>'
```

## Security Notes

- Cookies are equivalent to account credentials. Store them outside the repository.
- Do not paste cookie JSON into public issues, logs, or screenshots.
- Prefer `TWITTER_COOKIES_PATH` over inline JSON for long-running setups.
- Write tools can publish, delete, like, follow, block, and send DMs. Give agent access only when you intend to allow those actions.

## Troubleshooting

### The server starts but tools fail authentication

Re-export cookies after logging in to `x.com`. Make sure the exported cookies include both `auth_token` and `ct0`.

### Search or timeline tools suddenly fail

Twitter/X frequently changes private web API shapes and rate limits. Update this server and `xkit-py`, then retry with a fresh cookie export.

### My MCP client cannot find the command

Check that `uvx` is installed and available in the same environment used by the MCP client. For local development, install with `pip install -e .` and use `mcp-twitter-server`.

## Notes

Twitter/X frequently changes private web API response shapes. This server keeps
MCP-facing behavior defensive and delegates low-level protocol maintenance to
`xkit-py`.

## License

[MIT](LICENSE)
