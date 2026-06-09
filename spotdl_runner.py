"""Run spotdl with local compatibility patches applied."""

from SpotipyFree.Formatter import SpotifyFormatter
from spotdl.console.entry_point import entry_point


def _format_artist_with_nullable_visuals(artist):
    if not isinstance(artist, dict):
        return {
            "name": "",
            "id": "",
            "uri": "",
            "external_urls": {"spotify": ""},
            "images": [],
            "href": "",
            "genres": [""],
        }

    name = artist.get("profile", {}).get("name", "")
    uri = artist.get("uri", "")
    visuals = artist.get("visuals") or {}
    avatar = visuals.get("avatarImage") or {}
    return {
        "name": name,
        "id": uri.removeprefix("spotify:artist:"),
        "uri": uri,
        "external_urls": {
            "spotify": uri.replace(
                "spotify:artist:", "https://open.spotify.com/artist/"
            )
        },
        "href": uri.replace(
            "spotify:artist:", "https://api.spotify.com/v1/artists/"
        ),
        "images": avatar.get("sources", []),
        "genres": artist.get("genres", [""]),
    }


SpotifyFormatter.formatArtist = staticmethod(_format_artist_with_nullable_visuals)


if __name__ == "__main__":
    entry_point()
