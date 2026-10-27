# Quran Arabic Bot (Premiere Pro)

Lecture mein jahan Quran parha gaya, wahan ke liye Taj 13-line Mushaf (`E:\Quran\Chapter01.pdf … Chapter30.pdf`) se scan kaat kar ek-line transparent PNG (White + Black) banata hai. Phir unhein Premiere ki timeline par marker ki jagah laga deta hai.

Do hisse hain:

| Folder | Kaam |
|---|---|
| `quran-bot/` | Python bot: Whisper se sunna, ayat pehchanna, Mushaf se crop, PNG banana |
| `premiere-panel/` | Premiere Pro ka panel (UXP plugin): markers padhna, bot ko bhejna, PNG timeline par lagana |

Sab kuch muft hai aur aapke computer par chalta hai. Koi API key nahi chahiye.

## Ek dafa ka setup

1. **Code download karein:** GitHub par **Code → Download ZIP** dabayein aur ZIP ko kisi folder mein nikaal lein, jaise `D:\joji-app`.
2. **Python install karein** (agar nahi hai): https://www.python.org/downloads/ se. Install karte waqt **"Add python.exe to PATH"** par tick zaroor lagayein.
3. `quran-bot\install.bat` par double-click karein. Is mein kuch minute lagenge.
4. `quran-bot\config.json` Notepad mein kholein aur rasta check karein:
   - `quran_folder`: jahan `Chapter01.pdf … Chapter30.pdf` hain (`E:\\Quran`)
   - `output_folder`: jahan `Arabic Reference N` folder banenge
   - `whisper_model`: `medium` (achha aur theek raftaar). Zyada sahi chahiye to `large-v3` (dheema).
5. **Panel Premiere mein daalein:**
   - Creative Cloud app se **UXP Developer Tool** install karein.
   - Usmein **Add Plugin** dabayein aur `premiere-panel\manifest.json` chunein.
   - Premiere Pro (Beta) khula ho to **Load** dabayein.
   - Premiere mein **Window → UXP Plugins → Quran Arabic Bot** kholein.

## Har lecture par

1. `quran-bot\start_bot.bat` chalayein aur woh kaali window khuli rehne dein. Pehli dafa Whisper model (~1.5 GB) download hoga.
2. Premiere mein lecture ka sequence kholein. Quran wali jagahon par markers pehle se lage hon.
3. Panel mein **Markers parhein** dabayein, phir marker ka rang chunein (jaise Mauve).
4. Zaroorat ho to settings badlein:
   - **Audio track:** lecture ki awaaz kis track par hai (aam tor par 1)
   - **PNG video track:** PNG kis video track par lagani hai. Woh track sequence mein mojood hona chahiye.
5. **Quran PNG banao** dabayein. Panel mein har marker ka nateeja aata jayega. Aakhir mein PNGs ek naye bin mein import hokar timeline par lag jayengi.

Har marker ke liye bot:
- Marker ki jagah ki awaaz Whisper se sunta hai (thoda aage peeche ke saath).
- Sune hue alfaz ko poore Quran se milata hai. Jitna parha gaya, utna hi kaat-ta hai: ek lafz to ek lafz, poori ayat to ayat ke nishaan (۝) ke saath.
- Mushaf ke page se woh hissa kaat kar ek line mein jodta hai (right-to-left), aur White/Black transparent PNG banata hai.
- Hadith, dua aur durood jaise ghair-Qurani hisson ki PNG nahi banata. Woh `Timestamps_List.txt` mein alag list mein likhe jate hain.

Output folder: `E:\Quran\Arabic Reference N\White\…png`, `…\Black\…png` aur `Timestamps_List.txt`.

## Premiere ke baghair (command line)

Premiere se markers ke saath WAV export karke `quran-bot` folder mein:

```
.venv\Scripts\python cli.py lecture.wav --colors          (WAV mein kaun se rang ke markers hain)
.venv\Scripts\python cli.py lecture.wav --color mauve      (sirf Mauve markers)
.venv\Scripts\python cli.py lecture.mp4 --full             (markers nahi: poori audio sunna, dheema)
```

## Zaroori baatein

- **Pehla test:** yeh bot Premiere ke andar abhi tak chalaya nahi gaya, kyunki Premiere cloud par nahi chal sakta. Pehli dafa ek chhote sequence (3–4 markers) par try karein. Koi error aaye to panel ka message mujhe bhej dein.
- **Mushaf ka naqsha:** `quran-bot/data/indopak-13-lines-taj-company.db` (QUL se) batata hai ke kaunsa lafz kis page ki kis line par hai. Yeh `Chapter01.pdf` ke saath check kiya gaya hai: 338 lines mein ayat ke nishaan sahi mile. Mushaf ka page = naqshe ka page + 1, kyunki pehla page cover hai (`printed_offset` config mein). Agar kisi aur Para ke crop mein lines khiski hui milein, to mujhe batayein.
- **Shak:** jo lafz Quran mein kai jagah aata hai, ya jahan Whisper saaf na sun saka, list mein `(shak)` likha hoga. Unhein ek nazar dekh lein.
- **Timestamps** ek-do second aage peeche ho sakte hain.

## Data sources

- Page/line layout: Quranic Universal Library (QUL), "Indopak 13 lines - Taj company"
- Quran text (word numbering ke liye): Tanzil Uthmani text, CC BY 3.0, https://tanzil.net
