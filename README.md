# Ezan Vakti for Home Assistant

Diyanet prayer times (**ezan vakitleri**) for any country, city and district, plus the
**ezan** on any speaker Home Assistant can play to: Google/Nest, Sonos, Alexa (via
integrations), ESPHome and more.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tarikaltuncu&repository=ha-ezan-vakti&category=integration)

## What it does

- **Times for 200+ countries.** They come from Diyanet's monthly tables through
  [ezanvakti.emushaf.net](https://ezanvakti.emushaf.net). The integration refreshes them
  every 6 hours and keeps about 4 weeks on disk, so it keeps working through outages
  and offline restarts.
- **The ezan plays at Sabah, Öğle, İkindi, Akşam and Yatsı.** There is no ezan at
  İmsak or Güneş (sunrise).
- **The Sabah (Fajr) ezan wakes you before sunrise.** By default it plays 15 minutes
  before Güneş. This is adjustable, follows sunrise every day, and never plays earlier
  than İmsak.
- **Fasting days.** Turn on *Fasting* and the Sabah ezan plays at **İmsak** instead.
  *Fasting automatically in Ramadan* (on by default) does this for every day of Ramazan,
  using Diyanet's Hijri dates.
- **Recording styles.** Two Turkish sets with a different *makam* per vakit,
  plus Makkah, Madinah, Kuwait (Mishary Alafasy), Egyptian, Palestinian and Syrian.
  You can also pick Random, or Custom to use your own files.
- **Volume.** It plays at a set volume (default 30%) and puts the speaker's volume back
  afterwards. If your speaker supports announcements, it can play as one so your music
  resumes.
- **Presence (optional).** Pick a person, group, zone or binary sensor, and the ezan only
  plays when it is home or on. Leave it empty to always play.

## Install

1. In HACS, open **⋮ → Custom repositories** and add
   `https://github.com/tarikaltuncu/ha-ezan-vakti` with type **Integration**. You can
   also use the button above.
2. Install **Ezan Vakti**, then restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Ezan Vakti**.
4. Choose your country, city and district. If your district isn't listed, choose the
   city itself, because it covers the city centre.
5. Choose your speakers and a style. You can leave the speakers empty if you only want
   the times.

To change anything later, use **Settings → Devices & services → Ezan Vakti → Configure**.

## Entities

There is one device per location.

| Entity | What it is |
|---|---|
| `sensor.*_imsak`, `_sunrise`, `_dhuhr`, `_asr`, `_maghrib`, `_isha` | Today's vakits (timestamps) |
| `sensor.*_fajr_ezan` | When today's Sabah ezan plays |
| `sensor.*_next_ezan` | Next ezan (Fajr/Dhuhr/Asr/Maghrib/Isha), attribute `time` |
| `sensor.*_next_ezan_time` | Its timestamp, handy for a live countdown card |
| `sensor.*_time_to_next_ezan` | Minutes left, updated every minute (attribute `hh_mm`) |
| `sensor.*_hijri_date` | Diyanet's Hijri date |
| `binary_sensor.*_fasting_today` | Whether today's Sabah ezan is at İmsak |
| `switch.*_ezan`, `_fasting`, `_ramadan_auto_fasting` | The same settings as the options screen |
| `number.*_fajr_ezan_before_sunrise`, `_ezan_volume` | Same |
| `select.*_ezan_style` | Same |
| `button.*_play_next_ezan_now`, `_stop` | Test the ezan, or stop it |

The switches, numbers and select edit the same settings as the options screen, so you
can put them on a dashboard.

## Actions

- `ezan_vakti.play`: plays the ezan now. It takes optional `prayer`, `style` and
  `speakers`.
- `ezan_vakti.stop`: stops playback.
- `ezan_vakti.download_audio`: downloads recordings ahead of time. By default it
  downloads all styles. Otherwise each style is downloaded the first time it is used.

## Audio

**No recordings are stored in this repository.** The integration has a catalog of
public [archive.org](https://archive.org) links. Your Home Assistant downloads a style
into `<config>/ezan_vakti/<style>/` the first time you use it, and serves the files at
`/ezan_vakti/audio/…`. If `ffmpeg` is available (it is in the official images), every
file is loudness-normalised to -16 LUFS, so one volume setting sounds the same for
every style.

Turkish makam schemes. There is no single binding rule; these are the two most cited:

| Vakit | Şehitoğlu | Erarabacı |
|---|---|---|
| Sabah | Saba | Saba (İlhan Tok) |
| Öğle | Rast | Uşşak |
| İkindi | Hicaz | Rast |
| Akşam | Segâh | Segâh |
| Yatsı | Uşşak | Hicaz |

Styles that have no Fajr recording use Makkah's Fajr for the Sabah ezan. To use your
own recordings, choose **Custom** and enter a URL, a `/local/…` path or a
`media-source://…` id for the Fajr ezan and for the other prayers.

## Notes

- Times are shown in Home Assistant's time zone. Pick a location in the same time zone
  as your Home Assistant.
- Prayer-time data: Diyanet İşleri Başkanlığı, served by
  [ezanvakti.emushaf.net](https://ezanvakti.emushaf.net).
- Recordings belong to their reciters and uploaders. They are fetched from archive.org
  for personal use.

MIT licensed.
