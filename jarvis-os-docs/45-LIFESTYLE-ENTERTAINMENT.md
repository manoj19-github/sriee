# Lifestyle and Entertainment

## Goal

Sriee can remember explicit favourite songs, manage user-owned playlists, work with
approved provider/local sources, control playback and offer gentle contextual music
suggestions. The same subsystem stores reviewable hobbies, routine preferences,
celebration preferences and recommendation settings.

Everything is local-first and opt-in. A preference is not permission, listening is
not proof of preference, and a suggestion is not an instruction to play or write.

## Favourite songs and playlists

The favourite list stores ordered opaque track references plus source, added time
and explicit evidence. Users can say “favourite” or “favorite,” inspect the complete
list, reorder it, correct identity, remove one item, clear it with preview, export it
or delete it.

Playlists support user names such as Morning, Coding Deep Focus, Relax After Work,
Workout Energy, Study, Travel, Sleep, Meditation, Festival, Romantic, Old Memories
and Rainy Day. Generated playlists are proposals until confirmed. Provider writes,
imports, replacements and deletions use normal policy, approval and receipts.

## Sources

- Spotify, YouTube Music, YouTube, Apple Music and Amazon Music through separately
  installed, permissioned provider plugins.
- Local audio under user-selected registered roots such as a chosen Music folder.
- Provider credentials remain in an OS credential store or plugin boundary and are
  represented elsewhere only by opaque handles.
- Local indexing reads supported metadata beneath the exact root, blocks traversal
  and symlink escape, reconciles rename/deletion and does not upload audio.

## Playback

Typed media capabilities cover play, pause, resume, next, previous, seek, shuffle,
repeat, queue edits, safe volume, mute, fade, optional crossfade/gapless support and
a restart-safe sleep timer. Sriee does not bypass ads, DRM, provider prompts, account
limits or platform rules. Lyrics display is limited to licensed/provider-permitted
content; long copyrighted reproduction is prohibited.

Meeting volume ducking requires a user-enabled rule, a permitted meeting signal and
an immediate override. Volume increases are capped by the user’s accessibility and
safety preference.

## Contextual suggestions

Suggestions may use:

- an explicit request (“I want to relax”);
- a user-selected mode such as coding, focus, study, workout or wind-down;
- time/occasion when the matching routine is enabled;
- an approved repeated pattern;
- permitted weather/calendar context with freshness.

Suggestions never claim a mood from face, voice, screen, music or behavior. They are
capped, dismissible, quiet-hour aware and never start playback automatically.

## Analytics and privacy

Listening analytics are off by default and computed from selected local/provider
history. Reports may show most-played artist/track/playlist, skips and user-selected
activity tags. They do not score productivity, diagnose emotion or expose raw
history to unrelated prompts. Users can inspect, export and delete the data.

## Lifestyle preferences

Hobbies/interests, food/travel categories, routines, notification choices,
celebration style and recommendation topics are explicit, source-tagged and
correctable. A recommendation discloses its rationale, uncertainty and sponsorship
where known; it never purchases, subscribes, posts, messages or plays automatically.

## Future, not current allocation

Karaoke, playlist sharing, smart speakers, multi-room synchronization, AI-generated
audio and household/family profiles require separate provider, copyright, identity
and synchronization designs before function allocation.

## Function ownership

Runtime work is allocated under `230000–230017`. Scheduling and workflow templates
are under `210017–210020`; memory, plugins, policy and executor functions remain
authoritative for persistence, providers, permissions and side effects.
