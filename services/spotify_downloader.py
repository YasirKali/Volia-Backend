"""
Spotify downloader service using spotdl.
Handles extraction and zipping of Spotify playlist, album, and track content.

Metadata is fetched by scraping the Spotify embed page (fast and reliable).
Downloads are performed by invoking spotdl directly with individual track URLs
fetched via spotapi for complete playlist coverage.
"""

import asyncio
import os
import sys
import json
import glob
import re
import uuid
import shutil
import zipfile
import logging
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
from api.models import MediaInfo, FormatInfo, DownloadResponse
from services.base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class SpotifyDownloader(BaseDownloader):
    """Spotify downloader using spotdl CLI under the hood."""
    
    platform_name = "spotify"
    
    def _parse_spotify_url(self, url: str) -> tuple:
        """Parse a Spotify URL to extract the type (track/playlist/album) and ID."""
        # Clean query params
        clean_url = url.split('?')[0].rstrip('/')
        # Match patterns like open.spotify.com/playlist/ID or open.spotify.com/track/ID
        match = re.search(r'spotify\.com/(track|playlist|album)/([A-Za-z0-9]+)', clean_url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    async def _fetch_all_track_urls(self, entity_type: str, entity_id: str) -> tuple:
        """
        Fetch all track URLs and total count from a playlist/album using spotapi.
        Returns (total_count, list_of_track_urls).
        """
        import spotapi

        loop = asyncio.get_running_loop()

        def _fetch():
            if entity_type == "playlist":
                obj = spotapi.PublicPlaylist(entity_id)
                info = obj.get_playlist_info(limit=343, offset=0)
                content = info["data"]["playlistV2"]["content"]
                total = content["totalCount"]
                items = content.get("items", [])
                # Paginate if needed
                if total > 343:
                    offset = 343
                    while offset < total:
                        page = obj.get_playlist_info(limit=343, offset=offset)
                        page_items = page["data"]["playlistV2"]["content"].get("items", [])
                        items.extend(page_items)
                        offset += 343
                urls = []
                for item in items:
                    try:
                        uri = item["itemV2"]["data"]["uri"]
                        track_id = uri.removeprefix("spotify:track:")
                        urls.append(f"https://open.spotify.com/track/{track_id}")
                    except (KeyError, TypeError):
                        pass
                return total, urls
            elif entity_type == "album":
                obj = spotapi.PublicAlbum(entity_id)
                all_tracks = []
                for tracks in obj.paginate_album():
                    all_tracks.extend(tracks)
                urls = []
                for track in all_tracks:
                    try:
                        uri = track["track"]["uri"]
                        track_id = uri.removeprefix("spotify:track:")
                        urls.append(f"https://open.spotify.com/track/{track_id}")
                    except (KeyError, TypeError):
                        pass
                return len(urls), urls
            return 0, []

        return await loop.run_in_executor(None, _fetch)

    async def _fetch_embed_metadata(self, entity_type: str, entity_id: str) -> dict:
        """Fetch metadata from the Spotify embed page which returns structured JSON."""
        embed_url = f"https://open.spotify.com/embed/{entity_type}/{entity_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(embed_url, headers=headers)
            resp.raise_for_status()
        
        # Extract __NEXT_DATA__ JSON from the embed page
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>',
            resp.text
        )
        if not match:
            raise ValueError("Could not find metadata in Spotify embed page.")
        
        data = json.loads(match.group(1))
        entity = (
            data.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity", {})
        )
        if not entity:
            raise ValueError("Spotify embed page returned empty entity data.")
        
        return entity

    async def extract_info(self, url: str, cookies: Optional[str] = None) -> MediaInfo:
        """
        Extract playlist/album/track metadata from the Spotify embed page.
        This is fast and doesn't require spotdl or API credentials.
        """
        entity_type, entity_id = self._parse_spotify_url(url)
        if not entity_type or not entity_id:
            raise ValueError(f"Could not parse Spotify URL: {url}")
        
        try:
            entity = await self._fetch_embed_metadata(entity_type, entity_id)
        except Exception as e:
            logger.error(f"Error fetching Spotify embed metadata: {e}")
            raise ValueError(f"Spotify extraction failed: {str(e)}")
        
        title = entity.get("title") or entity.get("name") or "Spotify Download"

        # Get track list from embed (may be incomplete for large playlists)
        track_list = entity.get("trackList", [])
        total_songs = len(track_list)

        # For playlists/albums, fetch the real total count via spotapi
        if entity_type in ("playlist", "album"):
            try:
                real_total, _ = await self._fetch_all_track_urls(entity_type, entity_id)
                if real_total > total_songs:
                    total_songs = real_total
            except Exception:
                pass
        
        # Get subtitle (usually the artist or playlist owner)
        subtitle = entity.get("subtitle") or ""
        # For playlists, authors array holds the owner
        authors = entity.get("authors", [])
        uploader = authors[0].get("name") if authors else subtitle
        
        # Cover art
        cover_art = entity.get("coverArt", {})
        cover_sources = cover_art.get("sources", []) if isinstance(cover_art, dict) else []
        thumbnail = cover_sources[0].get("url") if cover_sources else None
        
        # Total duration from track durations (in ms)
        total_duration_ms = sum(t.get("duration", 0) for t in track_list)
        total_duration_sec = total_duration_ms / 1000.0 if total_duration_ms else None
        
        # Build format options
        formats = []
        if entity_type in ("playlist", "album") or total_songs > 1:
            formats.append(FormatInfo(
                format_id="all_songs",
                extension="zip",
                resolution=None,
                url=None,
                filesize=None,
                label=f"All Songs (ZIP) — {total_songs} tracks",
                has_video=False,
                has_audio=True,
            ))
        else:
            formats.append(FormatInfo(
                format_id="mp3",
                extension="mp3",
                resolution=None,
                url=None,
                filesize=None,
                label="Audio (MP3)",
                has_video=False,
                has_audio=True,
            ))
        
        description_parts = []
        if entity_type == "playlist":
            description_parts.append(f"Spotify playlist with {total_songs} tracks.")
        elif entity_type == "album":
            description_parts.append(f"Spotify album with {total_songs} tracks.")
        else:
            description_parts.append("Spotify track.")
        
        return MediaInfo(
            title=title,
            thumbnail=thumbnail,
            duration=total_duration_sec,
            uploader=uploader,
            description=" ".join(description_parts),
            platform="spotify",
            url=url,
            formats=formats,
            is_image=False,
        )
    
    async def download(self, url: str, format_id: str, output_dir: str, cookies: Optional[str] = None) -> DownloadResponse:
        """
        Download method wrapper around download_stream.
        Consumes the stream generator and returns the final response.
        """
        filename = None
        success = False
        message = ""
        
        async for event in self.download_stream(url, format_id, output_dir):
            if "data: " in event:
                data_str = event.replace("data: ", "").strip()
                try:
                    data = json.loads(data_str)
                    if data.get("status") == "complete":
                        success = True
                        filename = data.get("filename")
                    elif data.get("status") == "error":
                        success = False
                        message = data.get("message", "Download failed")
                except Exception:
                    pass
                    
        if success and filename:
            return DownloadResponse(
                success=True,
                filename=filename,
                message="Spotify download completed successfully!"
            )
        return DownloadResponse(
            success=False,
            filename=None,
            message=message or "Spotify download failed."
        )

    async def download_stream(self, url: str, format_id: str, output_dir: str):
        """
        Downloads Spotify content using spotdl and yields SSE progress events.
        Uses subprocess.Popen in a thread to avoid asyncio pipe issues on Windows.
        Handles large playlists (100+ songs) with proper timeout and error capture.
        """
        import subprocess
        import threading

        yield _sse(percent="5%", status="downloading", message="Initializing Spotify download...")

        temp_id = str(uuid.uuid4())[:8]
        songs_dir = os.path.join(output_dir, f"spotify_temp_{temp_id}")
        os.makedirs(songs_dir, exist_ok=True)

        # Parse URL to get a nice name for the zip
        entity_type, entity_id = self._parse_spotify_url(url)

        # Try to get the playlist/album name from the embed page (best effort)
        list_name = "Spotify Download"
        total_songs_hint = 0
        try:
            if entity_type and entity_id:
                entity = await self._fetch_embed_metadata(entity_type, entity_id)
                list_name = entity.get("title") or entity.get("name") or list_name
                track_list = entity.get("trackList", [])
                total_songs_hint = len(track_list)
        except Exception:
            pass

        # For large playlists, give a more informative initial message
        if total_songs_hint >= 100:
            yield _sse(percent="8%", status="downloading",
                        message=f"Large playlist detected ({total_songs_hint}+ tracks). This may take a while...")

        yield _sse(percent="10%", status="downloading",
                    message=f"Starting download of '{list_name}'...")

        # Fetch all track URLs via spotapi (proper pagination) instead of relying
        # on spotdl's internal playlist fetching which may miss tracks.
        track_urls = []
        if entity_type in ("playlist", "album") and entity_type and entity_id:
            try:
                total_from_api, track_urls = await self._fetch_all_track_urls(entity_type, entity_id)
                if track_urls:
                    total_songs_hint = total_from_api or len(track_urls)
                    yield _sse(percent="12%", status="downloading",
                                message=f"Found {len(track_urls)} tracks. Starting downloads...")
            except Exception as e:
                logger.warning(f"Failed to fetch individual track URLs, falling back to playlist URL: {e}")
                track_urls = []

        # Build spotdl command: use individual track URLs if available, otherwise fall back to playlist URL
        if track_urls:
            cmd_download = [
                sys.executable, "spotdl_runner.py", "download",
                *track_urls,
                "--output", os.path.join(songs_dir, "{title} - {artist}.{output-ext}"),
                "--threads", "4",
            ]
        else:
            cmd_download = [
                sys.executable, "spotdl_runner.py", "download", url,
                "--output", os.path.join(songs_dir, "{title} - {artist}.{output-ext}"),
                "--threads", "4",
            ]

        try:
            # Use subprocess.Popen in a thread to avoid asyncio pipe limitations on Windows
            loop = asyncio.get_running_loop()
            process_result = {"returncode": None, "stderr": ""}

            # For large playlists, split track URLs into batches to avoid command-line length limits.
            # A few batches can run in parallel; going too high tends to trigger throttling.
            batch_size = int(os.getenv("VOLIA_SPOTIFY_BATCH_SIZE", "10"))
            parallel_batches = int(os.getenv("VOLIA_SPOTIFY_PARALLEL_BATCHES", "3"))
            spotdl_threads = os.getenv("VOLIA_SPOTIFY_SPOTDL_THREADS", "4")
            batch_size = max(1, min(batch_size, 25))
            parallel_batches = max(1, min(parallel_batches, 6))
            if track_urls and len(track_urls) > batch_size:
                batches = [track_urls[i:i + batch_size] for i in range(0, len(track_urls), batch_size)]
            else:
                batches = None  # single command already built

            def _run_spotdl():
                try:
                    if batches:
                        def _run_batch(index, batch):
                            batch_cmd = [
                                sys.executable, "spotdl_runner.py", "download",
                                *batch,
                                "--output", os.path.join(songs_dir, "{title} - {artist}.{output-ext}"),
                                "--threads", spotdl_threads,
                            ]
                            proc = subprocess.Popen(
                                batch_cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                            )
                            _, stderr = proc.communicate()
                            return index, proc.returncode, stderr or ""

                        all_stderr = []
                        batch_returncodes = []
                        with ThreadPoolExecutor(max_workers=min(parallel_batches, len(batches))) as executor:
                            futures = [
                                executor.submit(_run_batch, index, batch)
                                for index, batch in enumerate(batches, start=1)
                            ]
                            for future in as_completed(futures):
                                index, returncode, stderr = future.result()
                                batch_returncodes.append(returncode)
                                if stderr:
                                    all_stderr.append(f"[batch {index}/{len(batches)}]\n{stderr}")
                        failed_codes = [code for code in batch_returncodes if code not in (0, None)]
                        process_result["returncode"] = failed_codes[0] if failed_codes else 0
                        process_result["stderr"] = "\n".join(all_stderr)
                    else:
                        proc = subprocess.Popen(
                            cmd_download,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                        )
                        _, stderr = proc.communicate()
                        process_result["returncode"] = proc.returncode
                        process_result["stderr"] = stderr or ""
                except Exception as e:
                    process_result["returncode"] = -1
                    process_result["stderr"] = str(e)

            # Start spotdl in a background thread
            thread = threading.Thread(target=_run_spotdl, daemon=True)
            thread.start()

            # Timeout: ~45 seconds per song, minimum 10 minutes
            max_timeout = max(600, total_songs_hint * 45) if total_songs_hint > 0 else 7200
            elapsed = 0
            stall_time = 0

            # Monitor progress by counting downloaded files
            last_count = 0
            while thread.is_alive():
                await asyncio.sleep(5)
                elapsed += 5

                # Count downloaded mp3 files
                mp3_files = glob.glob(os.path.join(songs_dir, "*.mp3"))
                downloaded_count = len(mp3_files)

                if downloaded_count != last_count:
                    last_count = downloaded_count
                    stall_time = 0
                    if total_songs_hint > 0:
                        percent_val = 10 + int((downloaded_count / total_songs_hint) * 80)
                        percent_val = min(percent_val, 90)
                    else:
                        percent_val = min(10 + downloaded_count * 2, 90)

                    yield _sse(
                        percent=f"{percent_val}%",
                        status="downloading",
                        message=f"Downloaded {downloaded_count}/{total_songs_hint or '?'} song(s)..."
                    )
                else:
                    stall_time += 5

                # A slow/problematic Spotify match can take several minutes without
                # creating a new file. Keep the subprocess alive and continue
                # streaming heartbeats instead of packaging a partial playlist.
                if stall_time > 30:
                    yield _sse(
                        percent=f"{percent_val if 'percent_val' in locals() else 90}%",
                        status="downloading",
                        message=f"Still resolving tracks... downloaded {downloaded_count}/{total_songs_hint or '?'} song(s)."
                    )
                    stall_time = 0
                if elapsed > max_timeout:
                    logger.warning(f"Spotify download timed out after {elapsed}s")
                    break

            # Give the thread a moment to finish if it's wrapping up
            thread.join(timeout=10)

            stderr_output = process_result["stderr"].strip()

            # Final count of downloaded files
            mp3_files = glob.glob(os.path.join(songs_dir, "*.mp3"))
            downloaded_count = len(mp3_files)

            if downloaded_count == 0:
                error_detail = stderr_output[:500] if stderr_output else f"exit code {process_result['returncode']}"
                yield _sse(status="error",
                           message=f"No songs were downloaded. spotdl error: {error_detail}")
                shutil.rmtree(songs_dir, ignore_errors=True)
                return

            if thread.is_alive():
                yield _sse(status="error",
                           message=f"Spotify download timed out after {elapsed}s with {downloaded_count}/{total_songs_hint or '?'} songs downloaded.")
                shutil.rmtree(songs_dir, ignore_errors=True)
                return

            # Package result
            safe_name = re.sub(r'[\\/*?:"<>|]', "", list_name).strip() or "Spotify"

            if downloaded_count > 1:
                yield _sse(percent="92%", status="downloading",
                           message=f"Zipping {downloaded_count} songs...")

                zip_filename = f"{safe_name}_{temp_id}.zip"
                zip_filepath = os.path.join(output_dir, zip_filename)

                def _create_zip():
                    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for mp3_path in mp3_files:
                            zf.write(mp3_path, os.path.basename(mp3_path))
                    return zip_filename

                final_filename = await loop.run_in_executor(None, _create_zip)
            else:
                # Single song — move it to the output dir
                src = mp3_files[0]
                base, ext = os.path.splitext(os.path.basename(src))
                final_name = f"{base}_{temp_id}{ext}"
                shutil.move(src, os.path.join(output_dir, final_name))
                final_filename = final_name

            # Clean up temp directory
            shutil.rmtree(songs_dir, ignore_errors=True)

            # Report partial success if not all songs were downloaded
            if total_songs_hint > 0 and downloaded_count < total_songs_hint:
                yield _sse(status="complete", percent="100%", filename=final_filename,
                           message=f"Downloaded {downloaded_count}/{total_songs_hint} songs (some may have failed).")
            else:
                yield _sse(status="complete", percent="100%", filename=final_filename)

        except Exception as e:
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error(f"Error during Spotify download/packaging: {error_msg}", exc_info=True)
            yield _sse(status="error", message=f"Download failed: {error_msg}")
            shutil.rmtree(songs_dir, ignore_errors=True)


def _sse(**kwargs) -> str:
    """Helper to build an SSE data line."""
    payload = {
        "percent": kwargs.get("percent", "0%"),
        "speed": kwargs.get("speed", "N/A"),
        "eta": kwargs.get("eta", "N/A"),
        "status": kwargs.get("status", "downloading"),
        "message": kwargs.get("message", ""),
    }
    if "filename" in kwargs:
        payload["filename"] = kwargs["filename"]
    return f"data: {json.dumps(payload)}\n\n"
