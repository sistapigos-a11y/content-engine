# 🎬 Content Engine — سيستام محتوى أوتوماتيكي (EN + ES)

كل يوم، بلا ما تدخل:

```
اختيار موضوع ← سكريبت وثائقي (20 دقيقة) ← تقييم وتحسين أوتوماتيكي ← تكييف للإسبانية
   ← تعليق صوتي ← لقطات فيديو مجانية ← مونتاج + موسيقى + ترجمة ← ثمبنيل
   ← 3 شورتس لكل لغة مع كابشن متحرك
   ← نشر: YouTube (طويل + Shorts)، TikTok، Instagram Reels، Facebook Reels
```

يخدم مجاناً على **GitHub Actions** (ما تحتاجش سيرفر ولا PC مشعول).

## الأدوات (كلها مجانية)

| المرحلة | الأداة | التكلفة |
|---|---|---|
| الكتابة | Google Gemini API (+ Groq احتياط) | مجاني (free tier) |
| الصوت | Microsoft Edge TTS | مجاني |
| اللقطات | Pexels + Pixabay | مجاني |
| المونتاج | ffmpeg | مجاني |
| التشغيل اليومي | GitHub Actions | مجاني |
| النشر | APIs الرسمية تاع كل منصة | مجاني |

---

## خطوات التركيب (مرة وحدة برك، ~ ساعة)

### 1) GitHub
1. اعمل حساب في github.com وأنشئ repository جديد (**Public** = دقائق Actions بلا حدود؛ Private = 2000 دقيقة/شهر وهذا ما يكفيش للفيديو اليومي).
2. ارفع هاذ الملفات فيه.
3. كل المفاتيح تتحط في: **Settings → Secrets and variables → Actions → New repository secret**.

### 2) مفاتيح الكتابة واللقطات
| Secret | منين تجيبو |
|---|---|
| `GEMINI_API_KEY` | aistudio.google.com → Get API key |
| `GROQ_API_KEY` | console.groq.com → API Keys (احتياط إذا Gemini طاح) |
| `PEXELS_API_KEY` | pexels.com/api |
| `PIXABAY_API_KEY` | pixabay.com/api/docs (بعد التسجيل) |

### 3) YouTube (قناة EN + قناة ES)
1. console.cloud.google.com → مشروع جديد → فعّل **YouTube Data API v3**.
2. **OAuth consent screen** → External → زيد إيميلك → ومن بعد اضغط **Publish app** (مهم! إذا تخليه في Testing الـ token يموت بعد 7 أيام).
3. **Credentials → Create OAuth client ID → Desktop app** → خذ `Client ID` و `Client secret`.
4. في الـ PC تاعك:
   ```bash
   pip install requests
   python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET
   ```
   اختار القناة الإنجليزية ← خذ الـ token. عاودها واختار القناة الإسبانية.
5. Secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN_EN`, `YT_REFRESH_TOKEN_ES`
6. ⚠️ **مهم:** مشاريع Google الجديدة الفيديوهات تاعها تترفع **Private** حتى تعمل **YouTube API Audit** (فورم مجاني: support.google.com/youtube/contact/yt_api_form). اعملو من النهار الأول، ياخذ من أسبوع لعدة أسابيع.
7. فعّل الحساب بالهاتف (youtube.com/verify) باش الثمبنيل يتحط أوتوماتيكياً.

### 4) TikTok
1. developers.tiktok.com → Create app → زيد **Content Posting API** (Direct Post) + **Login Kit**.
2. Secrets: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`، والـ refresh token لكل حساب: `TIKTOK_REFRESH_TOKEN_EN`, `TIKTOK_REFRESH_TOKEN_ES` (تجيبهم بـ Login Kit مرة وحدة، يدومو 365 يوم).
3. ⚠️ قبل ما TikTok يوافق على الـ app (audit)، الفيديوهات تنشر **خاصة (SELF_ONLY)**. بعد الموافقة زيد Variable اسمها `TIKTOK_PRIVACY` = `PUBLIC_TO_EVERYONE`.

### 5) Instagram + Facebook
1. حوّل Instagram لحساب **Professional (Business/Creator)** واربطو بـ Facebook Page.
2. developers.facebook.com → Create app (Business) → زيد Instagram Graph API.
3. خذ **Page Access Token طويل المدة** (ما يموتش) بالصلاحيات: `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement`, `publish_video`.
4. Secrets لكل لغة: `META_TOKEN_EN`, `IG_USER_ID_EN`, `FB_PAGE_ID_EN` (ونفسهم بـ `_ES`).

> أي منصة ما حطيتش المفاتيح تاعها، السيستام يفوتها بلا ما يطيح. تقدر تبدا بـ YouTube برك وتزيد الباقي من بعد.

### 6) التجربة الأولى
- **Actions → Daily content → Run workflow → mode: `quick`** ← فيديو تجريبي صغير بلا نشر. حمّلو من **Artifacts** وشوف الجودة.
- من بعد `no-publish` ← فيديو كامل بلا نشر.
- إذا عجبك: خلّيه، يخدم وحدو كل يوم على 13:17 UTC.

---

## التخصيص
كلش في `config.yaml`:
- `niche` — موضوع القناة (الأهم!)
- الأصوات: قائمة الأصوات المجانية: `edge-tts --list-voices`
- مدة الفيديو، عدد الشورتس، الوقت في `.github/workflows/daily.yml` (`cron`)
- موسيقى: حط ملفات mp3 بلا حقوق (YouTube Audio Library) في `assets/music/`
- خط الثمبنيل: حط `thumb.ttf` في `assets/fonts/`

## حدود لازم تعرفها
- **YouTube quota:** 10,000 وحدة/يوم، كل رفع = 1,600. الإعداد الافتراضي: طويل + شورت واحد لكل لغة = 4 رفعات = 6,400 ✅ (`youtube_shorts_per_video`). باقي الشورتس يروحو لـ TikTok/Instagram/Facebook. تحب أكثر؟ مشروع Google Cloud ثاني للقناة الإسبانية، أو اطلب زيادة quota في الـ audit.
- **سياسة يوتيوب (Inauthentic / mass-produced content):** القنوات اللي تنشر محتوى آلي متكرر بلا قيمة تتحرم من الربح. السيستام مصمم يقلل هاذ الخطر (سكريبت قصصي حقيقي، مراجعة جودة، إفصاح AI، صوت واضح)، لكن **نصيحتي** تشوف الفيديوهات الأولى قبل ما تخليه 100% وحدو، وتبدل `niche` لموضوع عندك فيه زاوية خاصة.
- **الحقائق:** الذكاء الاصطناعي يقدر يغلط. السيستام يطلب منه يتجنب الاختراع ويعلّم المعلومات المشكوك فيها، لكن مواضيع حساسة (صحة، سياسة، أشخاص أحياء) خليها برا الـ niche.
- **Edge TTS** خدمة مجانية غير رسمية من Microsoft — إذا يوماً توقفت، بدّل `engine/tts.py` لمزوّد آخر (ElevenLabs/Google TTS).

## هيكل المشروع
```
config.yaml              الإعدادات
run.py                   نقطة التشغيل
engine/writer.py         الموضوع، السكريبت، المراجعة، الإسبانية، الشورتس، العناوين
engine/llm.py            Gemini / Groq / Claude
engine/tts.py            الصوت
engine/media.py          لقطات Pexels / Pixabay
engine/render.py         المونتاج + الثمبنيل
engine/captions.py       الترجمة (SRT + كابشن متحرك)
engine/uploaders/        YouTube, TikTok, Instagram/Facebook
engine/pipeline.py       كل المراحل بالترتيب (ويكمّل وين حبس إذا صرا خطأ)
state/history.json       المواضيع اللي تنشرت (باش ما يعاودش)
```

تشغيل محلي:
```bash
pip install -r requirements.txt   # + ffmpeg
export GEMINI_API_KEY=... PEXELS_API_KEY=...
python run.py --quick --no-publish
```
