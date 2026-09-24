# Social Publishing (Phase 7)

## Safe mode

The default configuration is deliberately non-destructive:

```text
publishing_mode = mock
safe_publish_mode = true
publication_workflow = REVIEW
auto_publish = false
youtube_privacy_status = private
```

In this mode every platform uses `MockSocialPublisher`. No video or metadata is sent outside the computer.

## YouTube

1. Create a **Desktop app** OAuth client in Google Cloud.
2. Enable YouTube Data API v3.
3. Configure the local callback shown below in the OAuth client.
4. Set `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` in `.env`.

Callback:

```text
http://127.0.0.1:8000/publishing/oauth/youtube/callback
```

LiveClip requests `https://www.googleapis.com/auth/youtube.upload` plus OpenID profile identification. Uploads use the official resumable `videos.insert` endpoint. Development privacy defaults to `private`.

Official references:

- https://developers.google.com/youtube/v3/guides/uploading_a_video
- https://developers.google.com/identity/protocols/oauth2/native-app

## TikTok

1. Register an app in TikTok for Developers.
2. Add the Content Posting API product.
3. Configure Direct Post.
4. Request approval for `video.publish`.
5. Register the callback below.
6. Set `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env`.

Callback:

```text
http://127.0.0.1:8000/publishing/oauth/tiktok/callback
```

LiveClip requests `user.info.basic` and `video.publish`, and uploads local MP4 files using the official `FILE_UPLOAD` flow. TikTok requires explicit user consent before each Direct Post. Unaudited API clients remain restricted to private visibility.

Official references:

- https://developers.tiktok.com/docs/en/content-posting-api-get-started
- https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- https://developers.tiktok.com/docs/en/content-sharing-guidelines

## Instagram and Facebook

The adapters remain `PARTIALLY_SUPPORTED` in real mode and fully testable in mock mode. They intentionally do not invent endpoints or permissions. Real activation requires an approved Meta app, an eligible professional Instagram account and/or Facebook Page, the correct current permissions, and a media transfer method supported by the app configuration.

## Protected credentials

OAuth tokens are never stored in SQLite, frontend responses, or logs. SQLite stores only an opaque reference. Token payloads are encrypted for the current Windows user with DPAPI under `backend/storage/secrets`.

## Enabling real mode

After configuring and connecting official accounts, explicitly set:

```text
publishing_mode = real
safe_publish_mode = false
```

The UI requires a second confirmation before creating real publication jobs.
