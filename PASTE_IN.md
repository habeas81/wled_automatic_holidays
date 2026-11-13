# Paste-in presets (no scripts, no restore)

Use this if you only want a few of the looks, or you don't want to run anything. Each look below is a one-line
"API command" you paste into a WLED preset. Nothing here touches your segments: the looks apply to your existing
segment 0, whatever its length.

## How to add one look
1. In WLED open **Presets** and click **+ Create preset**.
2. Give it a name and tick **Use API command** (instead of "Save current state").
3. Paste the one-line JSON from below into the box and click **Save** (pick any free slot number).
4. Click the preset to try it. Tweak colours in WLED and save again if you like.

## How to make a playlist
Presets > **+ Create preset** > tick **Playlist**, then add the looks of one holiday in order. The suggested time per look and
a 7-second cross-fade are listed with each holiday. (Playlists cannot be pasted as text; they are built in the UI.)

Two things to know: palettes named `pal` 191-200 are custom palettes from `palette0.json`-`palette9.json` (upload them at
`http://<controller>/edit` first); if you skip that, those looks may show different colours. And the
scheduler (`wled_holiday_scheduler.py`) selects presets by slot number, so if you use it, use `--setup` instead of pasting.

*These pasted looks follow WLED's API-command format; I could not test the UI paste flow on every WLED version, so please report issues.*


## Thanksgiving
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Thanksgiving A - Colorwaves**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,0],[8,255,0],[0,0,255]],"fx":67,"sx":14,"ix":130,"pal":199}]}
```

**Thanksgiving B - Twinkle**
```json
{"on":true,"bri":160,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,0],[8,255,0],[0,0,255]],"fx":80,"sx":45,"ix":128,"pal":199}]}
```

**Thanksgiving C - Candle**
```json
{"on":true,"bri":140,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,0],[8,255,0],[0,0,255]],"fx":102,"sx":40,"ix":128,"pal":199}]}
```


## Valentine's
Playlist: 3 looks, 5 minutes each, 7-second cross-fade.

**Valentine A - Heartbeat**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[60,0,20],[255,60,140]],"fx":100,"sx":110,"ix":128,"pal":0}]}
```

**Valentine B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":195}]}
```

**Valentine C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":195}]}
```


## St. Patrick's Day
Playlist: 3 looks, 5 minutes each, 7-second cross-fade.

**St Pat A - Theater**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[0,0,0]],"fx":13,"sx":110,"ix":32,"pal":0}]}
```

**St Pat B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":194}]}
```

**St Pat C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":194}]}
```


## Armed Forces Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Armed Forces A - Scanner**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,40,255],[0,0,0],[255,170,0]],"fx":60,"sx":110,"ix":128,"pal":0,"o1":true}]}
```

**Armed Forces B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":191,"o1":true}]}
```

**Armed Forces C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":191,"o1":true}]}
```


## Memorial Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Memorial A - Tri Fade**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,0,255]],"fx":56,"sx":40,"ix":128,"pal":0}]}
```

**Memorial B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Memorial C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":67,"sx":40,"ix":128,"pal":5}]}
```


## Flag Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Flag A - Tri Wipe**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,0,255]],"fx":55,"sx":110,"ix":128,"pal":0}]}
```

**Flag B - Chase 3**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":54,"sx":90,"ix":128,"pal":0}]}
```

**Flag C - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```


## 4th of July
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**4th of July A - Fireworks**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[0,0,0],[0,0,255]],"fx":42,"sx":128,"ix":160,"pal":16}]}
```

**4th of July B - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```

**4th of July C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":67,"sx":80,"ix":128,"pal":5}]}
```


## Labor Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Labor Day A - Running Dual**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,40,255],[255,255,255],[255,90,0]],"fx":52,"sx":110,"ix":128,"pal":0}]}
```

**Labor Day B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,40,200],[255,100,0],[255,255,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Labor Day C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,40,200],[255,100,0],[255,255,255]],"fx":67,"sx":40,"ix":128,"pal":5}]}
```


## Columbus Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Columbus A - Chase 3**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[255,0,0]],"fx":54,"sx":128,"ix":128,"pal":0}]}
```

**Columbus B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[255,0,0]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Columbus C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[255,0,0]],"fx":67,"sx":40,"ix":128,"pal":5}]}
```


## Halloween
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Halloween A - Eyes**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,90,0],[70,0,130],[0,0,0]],"fx":82,"sx":128,"ix":128,"pal":0}]}
```

**Halloween B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,90,0],[140,0,255],[80,255,0]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Halloween C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,90,0],[140,0,255],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":5}]}
```


## Veterans Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Veterans A - Ripple**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[0,0,0],[0,0,255]],"fx":79,"sx":110,"ix":128,"pal":16}]}
```

**Veterans B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Veterans C - Scanner Dual**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[0,60,255],[0,0,0]],"fx":60,"sx":90,"ix":128,"pal":0,"o1":true}]}
```


## New Year's
Playlist: 2 looks, 15 minutes each, 7-second cross-fade.

**New Year A - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,170,0],[0,0,0],[200,200,255]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```

**New Year B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,170,0],[200,200,255],[0,0,0]],"fx":80,"sx":55,"ix":128,"pal":3}]}
```


## Easter
Playlist: 2 looks, 30 minutes each, 7-second cross-fade.

**Easter A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":196}]}
```

**Easter B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":196}]}
```


## USAF Birthday
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**USAF A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":193}]}
```

**USAF B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":193}]}
```

**USAF C - Running Dual**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,48,143],[255,255,255],[0,0,0]],"fx":52,"sx":90,"ix":128,"pal":3}]}
```


## USMC Birthday
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**USMC A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":192}]}
```

**USMC B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":40,"ix":128,"pal":192}]}
```

**USMC C - Running Dual**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[200,0,20],[255,176,0],[0,0,0]],"fx":52,"sx":90,"ix":128,"pal":3}]}
```


## MLK Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**MLK A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,90,255],[255,255,255],[255,176,0]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**MLK B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,90,255],[255,255,255],[255,176,0]],"fx":67,"sx":30,"ix":128,"pal":5}]}
```

**MLK C - Tri Fade**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,90,255],[255,255,255],[255,176,0]],"fx":56,"sx":40,"ix":128,"pal":5}]}
```


## Presidents Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Presidents A - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```

**Presidents B - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Presidents C - Chase 3**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":54,"sx":80,"ix":128,"pal":0}]}
```


## Patriot Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Patriot A - Tri Fade**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":56,"sx":25,"ix":128,"pal":5}]}
```

**Patriot B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,60,255]],"fx":67,"sx":20,"ix":128,"pal":5}]}
```

**Patriot C - Ripple**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[0,0,0],[0,60,255]],"fx":79,"sx":60,"ix":128,"pal":16}]}
```


## Cinco de Mayo
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Cinco A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[255,0,0]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Cinco B - Fiesta Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,120],[255,110,0],[255,220,0]],"fx":67,"sx":60,"ix":128,"pal":5}]}
```

**Cinco C - Chase 3**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[0,200,0],[255,255,255],[255,0,0]],"fx":54,"sx":100,"ix":128,"pal":0}]}
```


## Mardi Gras
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Mardi Gras A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,255],[0,200,40],[255,176,0]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Mardi Gras B - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,255],[0,200,40],[255,176,0]],"fx":67,"sx":50,"ix":128,"pal":5}]}
```

**Mardi Gras C - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[130,0,255],[0,200,40],[255,176,0]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```


## Groundhog Day
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Groundhog A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,170,40],[120,200,255],[255,255,255]],"fx":80,"sx":35,"ix":128,"pal":5}]}
```

**Groundhog B - Candle**
```json
{"on":true,"bri":150,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,170,40],[120,200,255],[255,255,255]],"fx":102,"sx":40,"ix":128,"pal":5}]}
```

**Groundhog C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,170,40],[120,200,255],[255,255,255]],"fx":67,"sx":20,"ix":128,"pal":5}]}
```


## Super Bowl
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Super Bowl A - Chase 3**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[139,69,19],[255,255,255],[255,176,0]],"fx":54,"sx":90,"ix":128,"pal":0}]}
```

**Super Bowl B - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,176,0],[255,255,255],[255,0,0]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```

**Super Bowl C - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[139,69,19],[255,176,0],[255,255,255]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```


## Team Game Nights
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Team Nights A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[200,16,46],[255,255,255],[0,40,120]],"fx":80,"sx":60,"ix":128,"pal":5}]}
```

**Team Nights B - Chase 3**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[200,16,46],[255,255,255],[0,40,120]],"fx":54,"sx":90,"ix":128,"pal":0}]}
```

**Team Nights C - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[200,16,46],[255,255,255],[0,40,120]],"fx":89,"sx":128,"ix":160,"pal":5}]}
```


## Birthday
Playlist: 3 looks, 15 minutes each, 7-second cross-fade.

**Birthday A - Twinkle**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":80,"sx":60,"ix":128,"pal":6}]}
```

**Birthday B - Starburst**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":89,"sx":128,"ix":160,"pal":6}]}
```

**Birthday C - Colorwaves**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,255,255],[0,0,0],[0,0,0]],"fx":67,"sx":60,"ix":128,"pal":6}]}
```


## Single looks (not in a playlist)

**Game Day (edit me)**
```json
{"on":true,"bri":128,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[255,255,255],[0,0,0]],"fx":67,"sx":128,"ix":128,"pal":5}]}
```

**Christmas**
```json
{"on":true,"bri":191,"transition":7,"seg":[{"id":0,"bri":255,"col":[[255,0,0],[0,200,0],[0,0,255]],"fx":80,"sx":55,"ix":128,"pal":198}]}
```
