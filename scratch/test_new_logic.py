import asyncio
import yt_dlp
from services.cookie_helper import get_ydl_opts_with_cookies

class DummySocialDownloader:
    def _format_filesize(self, size):
        if not size:
            return ""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _has_video_audio(self, f: dict) -> tuple[bool, bool]:
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        
        # Determine has_video
        if vcodec == 'none':
            has_video = False
        elif vcodec is not None:
            has_video = True
        else:
            resolution = f.get('resolution')
            height = f.get('height')
            width = f.get('width')
            has_video = bool(
                (height and height > 0) or 
                (width and width > 0) or 
                (resolution and resolution != 'audio only')
            )
            
        # Determine has_audio
        if acodec == 'none':
            has_audio = False
        elif acodec is not None:
            has_audio = True
        else:
            has_audio = True
            
        return has_video, has_audio

    def _get_format_label(self, f: dict) -> str:
        parts = []
        has_video, has_audio = self._has_video_audio(f)
        
        if has_video:
            height = f.get('height')
            width = f.get('width')
            if height:
                parts.append(f"{height}p")
            elif width:
                parts.append(f"{width}w")
        
        ext = f.get('ext', 'unknown')
        parts.append(ext.upper())
        
        if has_video and has_audio:
            parts.append("(Video+Audio)")
        elif has_video:
            parts.append("(Video Only)")
        elif has_audio:
            abr = f.get('abr')
            if abr:
                parts.insert(0, f"{int(abr)}kbps")
            parts.append("(Audio Only)")
        
        filesize = f.get('filesize') or f.get('filesize_approx')
        if filesize:
            size_str = self._format_filesize(filesize)
            if size_str:
                parts.append(f"~{size_str}")
        
        return " ".join(parts)

    def extract_info(self, info: dict):
        raw_formats = info.get('formats', [])
        formats = []
        seen_labels = set()
        
        video_only = []
        audio_only = []
        combined = []
        
        for f in raw_formats:
            ext = f.get('ext', 'unknown')
            has_video, has_audio = self._has_video_audio(f)
            url = f.get('url')
            
            if not url or ext in ('mhtml',):
                continue
            
            if has_video and has_audio:
                combined.append(f)
            elif has_video and not has_audio:
                video_only.append(f)
            elif has_audio and not has_video:
                audio_only.append(f)
        
        print(f"Counts: combined={len(combined)}, video_only={len(video_only)}, audio_only={len(audio_only)}")
        
        best_audio = None
        if audio_only:
            best_audio = max(
                audio_only,
                key=lambda a: (
                    1 if a.get('ext') in ('m4a', 'mp4', 'aac') else 0,
                    a.get('abr') or a.get('tbr') or 0,
                )
            )
            print(f"Best audio found: {best_audio.get('format_id')}")

        if best_audio:
            seen_heights = set()
            for vf in sorted(video_only, key=lambda x: (
                -(x.get('height') or 0),
                -(x.get('tbr') or 0),
            )):
                height = vf.get('height')
                if not height or height in seen_heights:
                    continue
                seen_heights.add(height)
                
                merged_id = f"{vf.get('format_id')}+{best_audio.get('format_id')}"
                ext = 'mp4'
                
                v_size = vf.get('filesize') or vf.get('filesize_approx') or 0
                a_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0
                total_size = (v_size + a_size) if (v_size and a_size) else None
                
                fps = vf.get('fps')
                parts = [f"{height}p"]
                if fps and fps > 30:
                    parts.append(f"{int(fps)}fps")
                parts.append("MP4")
                parts.append("(Backend Merge)")
                if total_size:
                    parts.append(f"~{self._format_filesize(total_size)}")
                
                label = " ".join(parts)
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                
                formats.append({
                    "format_id": merged_id,
                    "label": label,
                    "has_video": True,
                    "has_audio": True,
                })
        
        if not best_audio and video_only:
            seen_heights = set()
            for vf in sorted(video_only, key=lambda x: (
                -(x.get('height') or 0),
                -(x.get('tbr') or 0),
            )):
                height = vf.get('height')
                if not height or height in seen_heights:
                    continue
                seen_heights.add(height)
                
                label = self._get_format_label(vf)
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                
                formats.append({
                    "format_id": vf.get('format_id'),
                    "label": label,
                    "has_video": True,
                    "has_audio": False,
                })

        for f in combined:
            label = self._get_format_label(f)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            formats.append({
                "format_id": f.get('format_id'),
                "label": label,
                "has_video": True,
                "has_audio": True,
            })
            
        for f in audio_only:
            label = self._get_format_label(f)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            formats.append({
                "format_id": f.get('format_id'),
                "label": label,
                "has_video": False,
                "has_audio": True,
            })
            
        return formats

async def main():
    url = "https://x.com/Eminem/status/943590594491772928"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    downloader = DummySocialDownloader()
    formats = downloader.extract_info(info)
    print(f"\nFinal extracted formats count: {len(formats)}")
    for f in formats:
        print(f"Format: id={f['format_id']}, label={f['label']}, has_video={f['has_video']}, has_audio={f['has_audio']}")

if __name__ == "__main__":
    asyncio.run(main())
