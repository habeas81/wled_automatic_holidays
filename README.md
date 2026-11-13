# WLED Holiday Lights Scheduler

Runs a year-round holiday light schedule on a WLED controller. Every night it turns on the right holiday
preset at sunset and off at sunrise + 1 hour. About 30 holidays are covered (Valentine's, St. Patrick's,
Easter, Memorial Day, July 4th, Halloween, Thanksgiving, Christmas, New Year's, military birthdays and many more),
each with a 3-look rotating playlist and 7-second cross-fades.

It is one Python file with no packages to install (Python 3.8+), and everything you would want to change
lives in a plain text file, `wled_schedule.ini`. Tested end to end on Linux against a simulated controller; the
Windows steps (Task Scheduler, `.bat` files) use standard behavior but please confirm the reboot test.

## What is in the box
| File | What it is |
|---|---|
| `wled_holiday_scheduler.py` | The scheduler (do not need to edit it) |
| `wled_schedule.ini` | **Your settings. You must fill in 3 things (below).** |
| `presets.json` | **Default set.** 96 presets + playlists, *segment-agnostic*: no LED counts or segment positions, so the looks follow whatever segments you already have |
| `presets_sparkle.json` | **Optional alternative** with the 3-LED white sparkle overlay on the twinkle looks. Needs one continuous strip; built for 1196 LEDs |
| `PASTE_IN.md` | No-script option: each look as a one-line JSON you paste into a WLED preset, one at a time (nothing is overwritten) |
| `adjust_led_count.py` | Rescales `presets_sparkle.json` to your LED count (not needed for the default set) |
| `palette0.json` ... `palette9.json`, `PALETTES.txt` | The 10 custom colour palettes the presets use |
| `start_lights.bat`, `stop_lights.bat` | Windows start / stop shortcuts |

## Quick start (recommended): `--setup`
Put this whole folder somewhere permanent, open a terminal in it, and run:

    py -3 wled_holiday_scheduler.py --setup --dry-run     (shows the plan, changes nothing)
    py -3 wled_holiday_scheduler.py --setup               (asks for your controller address, then does it)

`--setup` will:
1. ask for your controller's address (and your latitude/longitude) and write them into `wled_schedule.ini`;
2. **back up your controller** (all presets and palettes) into a dated `wled_backup_...` folder next to the script;
3. read the preset slots you already use and add these presets and playlists **only into free slots** - none of your
   existing presets are changed. If one of ours would land on a slot you use, it is moved to a free one and the
   playlists that refer to it are renumbered;
4. upload the new `presets.json` and the palettes, and check they arrived;
5. write the final slot numbers into the `[presets]` section of the `.ini`, so the scheduler picks the right presets.

Things to know:
* WLED has only 10 custom palette slots. If you already use some, those palettes of ours are not installed and the looks
  that used them fall back to the built-in "Colors Only" palette (the setup tells you which). Your palettes are never overwritten.
* Keep `wled_setup_map.json` (written by setup). It lets you run `--setup` again later to update the presets in place instead of duplicating them.
* Setup merges `presets.json` (the segment-agnostic default). To install the optional sparkle set instead, run
  `py -3 wled_holiday_scheduler.py --setup --presets presets_sparkle.json` (use `adjust_led_count.py` first if your strip is not 1196 LEDs).
* `--setup` was tested against a simulated controller with deliberately colliding presets and palettes. It has not yet
  been run against many real setups, so please read the plan before saying yes. If anything looks off, your backup folder has everything needed to restore (Config > Security & Updates).

After setup run `--check` and `--status` (Step 3), then Step 4 to run it all the time. The manual route below does the same thing by hand.

## Manual route (if you prefer to do it yourself)

## Step 1 - Fill in the .ini (required)
Open `wled_schedule.ini` in any text editor. Three values are blank on purpose:

| Section / key | What to put | Example |
|---|---|---|
| `[controller]` `host` | Your WLED controller's IP address or hostname (check your router, or WLED's Info page). Give it a fixed/reserved IP. | `192.168.1.50` |
| `[location]` `latitude` | Your latitude, decimal degrees (north +, south -) | `41.88` |
| `[location]` `longitude` | Your longitude, decimal degrees (east +, **west -**; the US is negative) | `-87.63` |

Optional: `timezone` (a name like `America/Chicago` or `Europe/London`; blank uses the computer's own timezone;
on Windows `py -m pip install tzdata` makes named zones work, but blank is fine). Latitude/longitude only
drive the sunset/sunrise times, so a nearby city is accurate enough. Nothing is sent anywhere except HTTP
requests to your own controller on your own network.

Until host and location are filled in, the script refuses to run and tells you what is missing.

Other settings you may want (all optional, all in the same file): `sunset_offset_min` / `sunrise_offset_min`
(when to turn on/off relative to sunset/sunrise), the length of each holiday's window under `[windows]`,
`[birthdays]` (person = MM-DD, gets a 2-night look), `[custom_holidays]` (your own dates), `[events]`
(one-off events), `[ou]` (game-day nights for your favourite team: set `enabled = yes`, add a
`games_2027 = 09-04, 09-11, ...` line with your team's game dates, and edit preset slot 2 to your team colours),
and `[seasons]` (Thanksgiving, Christmas and so on). The windows are in US terms (Memorial Day, Thanksgiving,
Presidents Day...); edit the dates or windows if you want different holidays.

## Step 2 - Put the lights on your controller
1. **Pick a preset file.**
   * `presets.json` (default, recommended): the looks carry no `start`/`stop`, so they apply to your existing
     segment 0 whatever its length. Works on any strip length and layout; the twinkle looks are plain (no sparkle
     overlay). If you use several segments, only segment 0 is driven by a preset.
   * `presets_sparkle.json` (optional): adds three overlapping white-sparkle segments on the twinkle looks and on
     Christmas. It assumes **one continuous strip of 1196 LEDs**. For another length run
     `py adjust_led_count.py 600` (your count), which writes `presets_sparkle_600.json`, and restore that. Your
     WLED build must support at least 4 segments.
   Either way, the controller needs free flash: the default file is about 17 KB, the sparkle set about 29 KB (WLED
   Info page shows filesystem usage).
2. **Back up what you have** first: WLED -> Config -> Security & Updates -> *Backup presets* (and
   *Backup configuration*). Restoring presets replaces ALL of your existing presets.
3. **Upload the palettes.** Browse to `http://<your controller IP>/edit`, and upload `palette0.json` through
   `palette9.json` (file names must stay exactly as they are). WLED allows only 10 custom palettes, so any
   custom palettes you already have in those slots will be overwritten (the back-up above saves them).
   Palettes go in first, presets second.
4. **Restore the presets:** WLED -> Config -> Security & Updates -> *Restore presets* -> choose `presets.json`
   (or `presets_sparkle.json` / `presets_sparkle_<N>.json`). Reload the WLED page. You should see the holiday playlists, and tapping one plays it.
5. Preset slot numbers matter: the scheduler selects presets by number, and `[presets]` in the .ini lists them
   (e.g. Christmas = 14, Halloween = 12). If you restore your own presets later, keep these slots or edit the .ini.

## Step 3 - Test
Open a terminal (Windows: Command Prompt) in this folder:

    py -3 wled_holiday_scheduler.py --write-config   (only if wled_schedule.ini is missing)
    py -3 wled_holiday_scheduler.py --check          (validates the .ini)
    py -3 wled_holiday_scheduler.py --status         (tonight's plan and the next few nights, with sunset times)
    py -3 wled_holiday_scheduler.py --show 2027-01-01 2027-12-31    (the whole year's schedule)
    py -3 wled_holiday_scheduler.py --once --dry-run (what it would do right now, touching nothing)
    py -3 wled_holiday_scheduler.py --once           (apply tonight's state to the controller once)

On macOS/Linux use `python3` in place of `py -3`. If `--status` shows the right sunset time for your area and
`--once` changes the lights, you are done with setup.

## Step 4 - Run it all the time
The scheduler must stay running on an always-on computer (a PC, mini PC or Raspberry Pi on the same network).
It applies the right state at start-up, so a reboot or power cut heals itself, and with
`set_power_on_default = yes` it also stores tonight's preset as the controller's own power-on default.

**Windows:** put this folder somewhere permanent (e.g. `C:\wled\`; avoid external or removable drives). Open PowerShell
**as Administrator** (use a python.org install; the Microsoft Store Python cannot run at boot). Adjust the paths:

    $py = (Get-Command pythonw).Source ; $py
    $a = New-ScheduledTaskAction -Execute $py -Argument '"C:\wled\wled_holiday_scheduler.py"' -WorkingDirectory "C:\wled"
    $t = New-ScheduledTaskTrigger -AtStartup ; $t.Delay = 'PT1M'
    $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName "WLED Holiday Lights" -Action $a -Trigger $t -Settings $s -User "SYSTEM" -RunLevel Highest
    Start-ScheduledTask -TaskName "WLED Holiday Lights"

Remove later with `Unregister-ScheduledTask -TaskName "WLED Holiday Lights" -Confirm:$false`.

**Linux / Raspberry Pi:** run `python3 wled_holiday_scheduler.py` from a systemd service (`Restart=on-failure` is
optional; the script supervises itself) or from `@reboot` in crontab.

Stopping and starting: `stop_lights.bat` (or `--stop`) stops it cleanly and it stays stopped until you run
`start_lights.bat` or reboot; if it merely crashes it restarts itself after 30 s. Check `wled_scheduler.log` (next to
the script) if anything looks wrong: "WLED unreachable" just means the controller or network was down, and it
keeps retrying.

## Everyday use
* Edit `wled_schedule.ini` and save; the running scheduler picks it up at its next wake-up, or at once with
  `py -3 wled_holiday_scheduler.py --reload`. No restart. A mistake is logged and ignored, the last good settings stay.
* Moving holidays (Memorial Day, Thanksgiving, Easter, ...) are calculated automatically; Super Bowl and your
  team's nights need dates added under `[custom_holidays]` / `[ou]` each year.
* Want to change a look? Edit the preset in WLED (keep its slot number), or change its slot in `[presets]`.
* Wake pattern: hourly by day (clock check only), every 15 minutes from an hour before sunset until sunrise + 1 h.

## Troubleshooting
* *"Not configured yet"*: fill in the blanks from Step 1.
* *Sunset time is wrong by hours*: check the sign of your longitude and (optionally) set `timezone`.
* *Wrong colours / a palette looks odd*: the palettes were not uploaded (Step 2.3) before restoring presets.
* *Lights don't change*: `--once` and read the output; confirm you can open `http://<host>/` in a browser from that computer.
* Leftover overlay segments after switching sets: if you used the sparkle set and then restore the default one, apply any look from the sparkle set once (each single-segment look removes the overlays) or delete segments 1-3 in the WLED Segments tab.
* Segment-agnostic presets keep your current segment bounds, grouping and spacing. They were tested on WLED 16.0.1; other versions are untested, so please report what you find.
