# yt-dlp Webshare Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Webshare residential proxy support to yt-dlp extraction while keeping cookies disabled by default and using existing cache, single-flight, circuit breaker, and concurrency protections.

**Architecture:** Proxy country/sticky-session behavior is owned by Webshare configuration and the `YTDLP_PROXY_URL` environment variable. The backend only passes the configured proxy URL to yt-dlp, disables cookies unless explicitly enabled, and moves retry/backoff from hardcoded constants to settings.

**Tech Stack:** FastAPI, Pydantic Settings, yt-dlp, pytest.

---

### Task 1: Audio Extraction Proxy And Cookie Policy

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/audio.py`
- Test: `tests/services/test_audio_subtitle_inline.py`

- [ ] **Step 1: Write failing tests**

Add tests proving that `extract_audio()` passes `settings.ytdlp_proxy_url` as the yt-dlp `proxy` option, disables cookies by default, and only uses `youtube_cookies_path` when `settings.ytdlp_use_cookies` is true.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/services/test_audio_subtitle_inline.py -v`

Expected before implementation: failure because `Settings` does not expose `ytdlp_proxy_url` / `ytdlp_use_cookies`, or because `extract_audio()` does not set the expected options.

- [ ] **Step 3: Implement settings and yt-dlp options**

Add settings:

```python
ytdlp_proxy_url: str = ""
ytdlp_proxy_country: str = ""
ytdlp_use_cookies: bool = False
```

Update `extract_audio()` so `ydl_opts["proxy"]` is set only when `ytdlp_proxy_url` is configured. Set `ydl_opts["nocookies"] = True` unless `ytdlp_use_cookies` is true and a cookie file exists.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/services/test_audio_subtitle_inline.py -v`

Expected after implementation: all tests pass.

### Task 2: Retry/Backoff Settings

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/routers/extract.py`
- Test: `tests/routers/test_extract_errors.py`

- [ ] **Step 1: Write failing test**

Add a router test proving retryable yt-dlp errors honor `settings.ytdlp_retry_count` and `settings.ytdlp_backoff_seconds`.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/routers/test_extract_errors.py -v`

Expected before implementation: failure because retry count/backoff are hardcoded.

- [ ] **Step 3: Implement settings-driven retry**

Add settings:

```python
ytdlp_retry_count: int = 1
ytdlp_backoff_seconds: float = 1.0
```

Replace `_RETRY_BACKOFF_SEC` with `settings.ytdlp_backoff_seconds` and retry retryable `YtDlpClassifiedError` up to `settings.ytdlp_retry_count` times.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/routers/test_extract_errors.py -v`

Expected after implementation: all tests pass.

### Task 3: Environment Documentation

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add Webshare env examples**

Document `YTDLP_PROXY_URL`, `YTDLP_PROXY_COUNTRY`, `YTDLP_USE_COOKIES`, `YTDLP_RETRY_COUNT`, and `YTDLP_BACKOFF_SECONDS`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: all tests pass.
