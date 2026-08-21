# Fergie Seasonal Event System

Fergie's seasonal system provides reusable, date-controlled events
without hard-coding each holiday story directly into the main bot logic.

Seasonal packages live under:

seasonal/`<season>`{=html}/`<year>`{=html}/

Examples:

seasonal/halloween/2026/ seasonal/christmas/2026/
seasonal/halloween/2027/

Each package can define its own:

-   active dates
-   timezone
-   story stages
-   binary/puzzle clues
-   media
-   jumpscares
-   rescue conditions
-   personalized reactions
-   seasonal voice corruption / performance modes
-   post-event behavior

The Python seasonal engine is shared between packages.

------------------------------------------------------------------------

# Halloween 2026

Package:

seasonal/halloween/2026/

State key:

seasonal:halloween:2026

Timezone:

America/New_York

The Halloween 2026 event has two major phases.

## September --- The TOR Incident

September contains the interactive story.

General progression:

-   Sep 1--3: normal Halloween excitement / costume behavior
-   Sep 4--7: TOR curiosity
-   Sep 8--11: first corruption
-   Sep 12--16: realization that the real Fergie is trapped
-   Sep 17--20: corruption fights back
-   Sep 21--23: identity / sourdough revelation
-   Sep 24--30: rescue window

Fergie continues responding normally through Gemini.

Seasonal events occur AFTER her normal response and never replace normal
conversation.

During the story, binary transmissions can leak into conversations.

Players must decode and solve the clues to progress.

Decoder hints become increasingly obvious if the crew remains stuck.

Once the decoder has been discovered, tutorial hints stop.

The final clue unlocks rescue attempts.

The final binary clue itself does NOT rescue Fergie.

A member must conversationally remind Fergie who she is and include the
configured identity anchor.

For Halloween 2026, that identity anchor is:

sourdough

A bare message containing only "sourdough" is not enough.

The successful Discord user becomes the canonical rescuer and is
persisted in seasonal state.

Special users can receive personalized rescue reactions by Discord user
ID.

Unknown users receive a configured default reaction.

After rescue:

-   story_completed becomes true
-   the rescuer is permanently recorded
-   September binary stops
-   September corruption stops
-   rescue attempts close
-   Fergie's post-rescue story is posted
-   normal Fergie continues operating

## September Seasonal Voice Corruption

Fergie's ElevenLabs voice is part of the September corruption story.

The system preserves Fergie's normal voice identity while allowing the
delivery to become corrupted during eligible September story stages.

Supported voice modes:

-   normal --- standard Fergie delivery
-   whisper --- quiet, close, unsettling delivery
-   scared --- nervous / frightened delivery
-   hollow --- flat, slowed, emotionally empty delivery
-   possessed --- aggressive / corrupted delivery
-   unstable --- delivery changes within the same spoken line

The corruption chance increases as the September story progresses:

-   Stage 0 (Sep 1--3): 0%
-   Stage 1 (Sep 4--7): 0%
-   Stage 2 (Sep 8--11): 8%
-   Stage 3 (Sep 12--16): 15%
-   Stage 4 (Sep 17--20): 22%
-   Stage 5 (Sep 21--23): 28%
-   Stage 6 (Sep 24--30): 35%

The voice system is fail-safe:

-   it is dormant outside the eligible September story window
-   story_completed immediately disables seasonal voice corruption
-   after rescue, spoken Fergie returns to normal
-   an unavailable/erroring seasonal voice endpoint falls back to normal
-   explicit existing whisper cues remain supported
-   seasonal voice decisions never advance clues or modify story
    progress

The same seasonal voice treatment can affect Fergie's spoken output
across:

-   text-channel ElevenLabs audio / `@Fergie say ...`
-   normal VC conversation
-   spoken DJ commentary and DJ intros

DJ music playback itself is not modified. When Fergie speaks while
DJing, the existing DJ speech/mixing path is used.

Architecture:

1.  Python owns seasonal eligibility, story state, stage, corruption
    probability, and the selected voice mode.
2.  The protected read-only `/seasonal-voice` bridge endpoint exposes
    one voice decision to the Node VC/DJ service.
3.  Node performs the selected delivery through ElevenLabs.
4.  Normal speech uses ElevenLabs Flash v2.5.
5.  Corrupted performance modes use Eleven v3.
6.  Any seasonal voice failure falls back to normal speech rather than
    breaking VC.

------------------------------------------------------------------------

# October --- Halloween Mode

October is separate from the September TOR story.

Normal Fergie continues operating.

During eligible conversations, rare Halloween jumpscares may occur.

Halloween jumpscares:

-   occur only during conversations with Fergie
-   never replace her normal Gemini response
-   use configured probability
-   obey conversation spacing
-   obey media cooldowns
-   stop when the configured seasonal window ends

There are no random standalone 3 AM jumpscare posts.

------------------------------------------------------------------------

# Media

Halloween 2026 media is stored under:

seasonal/halloween/2026/media/

Current categories include:

media/costume/ media/corruption/ media/jumpscares/

Media behavior is controlled by seasonal JSON rather than hard-coded
individual GIF paths throughout bot.py.

This allows media to be replaced or expanded without rebuilding the
entire seasonal engine.

------------------------------------------------------------------------

# Configuration

Halloween 2026 configuration is stored under:

seasonal/halloween/2026/config/

Important files include:

## season.json

Controls the seasonal package itself, including activation windows,
timezone, package identity, and major event settings.

## september_story.json

Controls the September story progression, stages, rescue configuration,
and post-rescue story.

## binary_clues.json

Controls the binary puzzle sequence, accepted solutions, clue
progression, and decoder hints.

## media_events.json

Defines seasonal media assets, paths, contexts, stage restrictions,
cooldowns, jumpscare behavior, and October conversational scares.

## rescue_reactions.json

Contains Discord-user-specific rescue reactions and fallback responses.

Personalized reactions should be keyed by Discord user ID, not display
name.

------------------------------------------------------------------------

# Hidden Admin/Test Commands

Seasonal testing commands are intentionally hidden from the public
command reference.

They require:

1.  FERGIE_ADMIN_USER_ID
2.  FERGIE_TEST_CHANNEL_ID

Unauthorized users receive no seasonal admin functionality.

## !seasonreload

Reload seasonal JSON packages.

Example:

!seasonreload

Expected result:

seasonal reload complete. packages=1 errors=0

Use after changing seasonal JSON and redeploying.

------------------------------------------------------------------------

## !seasonconfig

Validate the currently loaded seasonal package.

Example:

!seasonconfig

Halloween 2026 should report:

SEASON CONFIG ✅ halloween_2026 loaded cleanly. clues=7 media=7

This checks package structure and required media paths.

------------------------------------------------------------------------

## !seasonstatus

Inspect current persisted seasonal state.

Example:

!seasonstatus

Before September 1, Halloween 2026 should show approximately:

season_id: halloween_2026 state_key: seasonal:halloween:2026 package:
halloween/2026 active_window: none date_stage: none story_completed:
False completed_clues: \[\] rescuer: None

This command does not modify progress.

------------------------------------------------------------------------

## !seasonmedia

Preview a seasonal media asset without changing canonical story
progress.

Examples:

!seasonmedia ghost_fergie_hover

!seasonmedia evilferg_full_jumpscare

Use this to verify that deployed media paths and Discord uploads work.

------------------------------------------------------------------------

## !seasonclue

Preview a configured binary clue without solving it or changing story
progress.

Example:

!seasonclue help

Expected Halloween 2026 test:

01001000 01000101 01001100 01010000

Decoded reference:

HELP

This command is for administrator verification only.

------------------------------------------------------------------------

## !seasonvoice

Test or inspect the Python/text-audio seasonal voice system without
advancing canonical story progress.

Status:

``` text
!seasonvoice status
```

Forced text-audio tests:

``` text
!seasonvoice normal testing one two three
!seasonvoice whisper don't look behind you
!seasonvoice scared mom... can you hear me?
!seasonvoice hollow everything is fine
!seasonvoice possessed you should not have opened that
!seasonvoice unstable I said I'm fine
```

Forced modes are administrator tests only and do not alter seasonal
story state.

## /seasonvoicetest

Test the Node VC/DJ ElevenLabs seasonal voice modes directly in voice
chat.

Fergie must already be connected to VC.

Examples:

``` text
/seasonvoicetest mode:normal
/seasonvoicetest mode:whisper
/seasonvoicetest mode:scared
/seasonvoicetest mode:hollow
/seasonvoicetest mode:possessed
/seasonvoicetest mode:unstable
```

The optional `text` argument can force custom test dialogue.

Example:

``` text
/seasonvoicetest mode:unstable text:Everything is completely normal I promise.
```

When DJ music is active, the test uses the existing DJ speech mixer so
the voice can be verified while music is playing.

This command forces only the requested voice performance. It does not
advance clues, alter rescue state, or change the seasonal schedule.

------------------------------------------------------------------------

# IMPORTANT --- Testing Safety

The preview commands are designed not to advance canonical story
progress.

Do not manually edit production seasonal state unless absolutely
necessary.

Do not mark clues solved through database edits.

Do not manually set a rescuer.

The real event should determine its own canonical rescuer.

A destructive seasonal reset command is intentionally not provided by
default.

------------------------------------------------------------------------

# Creating Future Seasonal Events

Do NOT duplicate the entire seasonal Python engine for each event.

Create a new seasonal package instead.

Example:

seasonal/christmas/2026/

Possible structure:

seasonal/christmas/2026/ ├── config/ │ ├── season.json │ ├── story.json
│ ├── clues.json │ ├── media_events.json │ └── reactions.json └── media/
├── costumes/ ├── story/ └── jumpscares/

The package should provide the content.

The shared Python engine should provide the mechanics.

Only extend bot.py when a future event requires a genuinely new mechanic
that cannot be represented by the existing seasonal configuration
system.

------------------------------------------------------------------------

# Design Rule

Seasonal code must never break normal Fergie.

Normal conversation should complete first.

Seasonal processing occurs afterward.

Seasonal exceptions must be isolated so Gemini conversation continues
even if a seasonal package has a problem.

When no seasonal window is active, seasonal functionality should remain
dormant.

------------------------------------------------------------------------

# Halloween 2026 Pre-Launch Checklist

Before September 1:

-   !seasonreload reports packages=1 and errors=0
-   !seasonconfig passes
-   clue count is 7
-   media count is 7
-   !seasonstatus shows the correct package/state
-   Ghost Fergie media preview works
-   Evil Fergie jumpscare preview works
-   binary HELP preview decodes correctly
-   normal Gemini conversation still works
-   voice replies still work
-   !seasonvoice status reports the expected seasonal voice profile
-   !seasonvoice forced tests work for normal, whisper, scared, hollow,
    possessed, and unstable
-   /seasonvoicetest works in VC for all six modes
-   /seasonvoicetest works while DJ music is active
-   seasonal voice failures fall back to normal speech
-   rescued/completed story state disables random seasonal voice
    corruption
-   existing reaction GIF behavior still works
-   no seasonal content triggers before the configured activation window

Once these checks pass, leave the production seasonal state untouched
and allow the event to begin naturally.
