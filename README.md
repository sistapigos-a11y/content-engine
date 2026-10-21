# 🎬 Content Engine — سيستام محتوى أوتوماتيكي (EN + ES)

كل يوم، بلا ما تدخل:

```
ترندات اليوم (Wikipedia + Google Trends)
  ← اختيار قصة (شخصية مشهورة حالياً / لغز)       مثال: "Xavi Warned Us 3 Years Ago"
  ← بحث من Wikipedia (حقائق حقيقية) ← سكريبت 20 دقيقة ← مراجعة + تدقيق حقائق ← نسخة إسبانية
  ← صوتك أنت (نسخة AI من صوتك) بالإنجليزية والإسبانية
  ← صور الشخصيات (Wikimedia Commons) + لقطات b-roll + نصوص متحركة + بطاقات الفصول
  ← مونتاج بـ Remotion ← ثمبنيل "NOBODY [الشخص] BELIEVED"
  ← 3 شورتس لكل لغة مع كابشن كلمة بكلمة
  ← نشر: YouTube (طويل + Shorts)، TikTok، Instagram Reels، Facebook Reels
```

يخدم مجاناً على **GitHub Actions**: الإنجليزية والإسبانية يتمونتجو **في نفس الوقت** (جوج machines).

---

## 🎙️ 1) صوتك (أهم خطوة)

سجّل **15 إلى 30 ثانية** بصوتك (بلاصة هادية، ميكرو قريب، بلا موسيقى) بنفس الأسلوب اللي تحب يكون فيه الفيديو.

الصوت يتحط **مشفّر** في `assets/voice/me.wav.enc`، باش حتى واحد ما يقدر ينسخ صوتك من الـ repository (راهو Public).
المفتاح يتحط في Secret اسمو `VOICE_KEY`، والـ workflow يفك التشفير وقت الخدمة برك.

تبدّل التسجيل؟
```bash
openssl enc -aes-256-cbc -pbkdf2 -salt -in me.wav -out assets/voice/me.wav.enc -pass pass:VOICE_KEY_تاعك
```
اختياري: `me_es.wav.enc` للإسبانية (نفس الطريقة، ويتفك لـ `me_es.wav`).

**جرّب الصوت قبل كلش:** Actions → Daily content → Run workflow → mode: `voice-test` ← حمّل `voice-test` من Artifacts واسمع.

| الخيار | التكلفة | الجودة | السرعة |
|---|---|---|---|
| `chatterbox` (الافتراضي) | مجاني، open-source (MIT) | مليحة | بطيء على CPU (~1-2 ساعة لفيديو 20 دقيقة) |
| `elevenlabs` | مدفوع: فيديو 20 دقيقة × جوج لغات = ~40 دقيقة صوت في النهار، والخطط الرخيصة ما تكفيش | ممتازة | سريع |

لـ ElevenLabs: اعمل **Instant Voice Clone** في الموقع، حط `ELEVENLABS_API_KEY` و `ELEVENLABS_VOICE_ID` في Secrets، وبدّل `voice.provider: elevenlabs` في `config.yaml`.

> ⚠️ استعمل صوتك أنت برك. نسخ صوت شخص آخر بلا إذنو ممنوع في كل المنصات.

---

## 🎨 2) المونتاج — Remotion (`video/`)

```
video/src/
  Video.tsx                 التركيب الرئيسي (طويل 1920×1080 + شورت 1080×1920)
  components/Shots.tsx      الصور (Ken Burns + خلفية blur) واللقطات (zoom خفيف)
  components/SceneView.tsx  نص متحرك، اقتباسات، بطاقات الفصول
  components/Captions.tsx   كابشن الشورتس (الكلمة اللي تنقال بالأحمر)
  Thumbnail.tsx             الثمبنيل: كلمة يسار + الشخص في الوسط + كلمة يمين + شخص ثاني بالأحمر
  fonts.ts                  Anton + Montserrat (محليين، ما يحتاجوش انترنت)
```

بدّل الستايل كيما تحب (الألوان، الخطوط، الحركات) — Python غير يبعث `props.json`.

**تشوف فيديو حقيقي في Studio وتعدّل عليه مباشرة:**
```bash
cd video && npm install
npx remotion studio --props=../work/<JOB>/en/long/props.json --public-dir=../work/<JOB>/en/long
```

اللون الرئيسي: `style.accent` في `config.yaml`.

---

## 🔥 3) النيش: شخصيات ترند + ألغاز

في `config.yaml` ← `channel.formats`:
- `trending_person` (weight 2): كل يوم يشوف شكون راهو ترند (أكثر صفحات Wikipedia مشاهدة البارح + Google Trends في US/GB/MX/ES/AR)، ويختار لاعب / ستريمر / يوتيوبر / رابر عندو قصة: "Nobody Believed"، "Was Right All Along"، "The Rise of".
- `mystery` (weight 1): النيش القديم.

بدّل الـ weights كيما تحب (مثلاً `mystery: 0` = غير شخصيات).

**الصور:** من Wikimedia Commons برك (مرخّصة للاستعمال)، والحقوق تتكتب أوتوماتيكياً في الوصف. ما يستعملش كليبات من يوتيوب ولا من الماتشات، لأنها تجيب copyright strikes.

---

## ⚙️ 4) التركيب (مرة وحدة)

### GitHub
1. أنشئ repository **Public** (Actions بلا حدود؛ Private ما يكفيش).
2. ارفع الملفات + `assets/voice/me.wav`.
3. المفاتيح في: **Settings → Secrets and variables → Actions**.

### المفاتيح
| Secret | منين | ضروري؟ |
|---|---|---|
| `GEMINI_API_KEY` | aistudio.google.com | ✅ |
| `GROQ_API_KEY` | console.groq.com | احتياط |
| `PEXELS_API_KEY` | pexels.com/api | ✅ |
| `PIXABAY_API_KEY` | pixabay.com/api/docs | مستحسن |
| `HF_TOKEN` | huggingface.co/settings/tokens | مستحسن (تحميل موديل الصوت أسرع) |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | elevenlabs.io | غير إذا اخترت ElevenLabs |

### YouTube (قناة EN + قناة ES)
1. console.cloud.google.com ← مشروع جديد ← فعّل **YouTube Data API v3**.
2. **OAuth consent screen** ← External ← **Publish app** (إذا يبقى Testing الـ token يموت بعد 7 أيام).
3. **Credentials ← OAuth client ID ← Desktop app**.
4. في الـ PC: `python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET` ← اختار القناة الإنجليزية، ومن بعد عاود للإسبانية.
5. Secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN_EN`, `YT_REFRESH_TOKEN_ES`
6. ⚠️ اعمل **YouTube API Audit** (support.google.com/youtube/contact/yt_api_form). قبل الموافقة الفيديوهات تترفع **Private**.
7. فعّل القناة بالهاتف (youtube.com/verify) باش الثمبنيل يتحط.

### TikTok
developers.tiktok.com ← app ← **Content Posting API** + **Login Kit**.
Secrets: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN_EN`, `TIKTOK_REFRESH_TOKEN_ES`.
⚠️ قبل الـ audit الفيديوهات تكون خاصة. بعد الموافقة: Variable `TIKTOK_PRIVACY` = `PUBLIC_TO_EVERYONE`.

### Instagram + Facebook
حساب Instagram **Professional** مربوط بـ Facebook Page ← developers.facebook.com ← **Page Access Token طويل المدة** (`instagram_content_publish`, `pages_manage_posts`, `publish_video`).
Secrets: `META_TOKEN_EN`, `IG_USER_ID_EN`, `FB_PAGE_ID_EN` (ونفسهم بـ `_ES`).

> أي منصة بلا مفاتيح يفوتها السيستام بلا ما يطيح.

---

## ▶️ 5) التشغيل

**Actions → Daily content → Run workflow**:
| mode | واش يدير |
|---|---|
| `voice-test` | جملتين بصوتك (EN + ES) |
| `quick` | فيديو صغير بالإنجليزية بلا نشر |
| `no-publish` | فيديو كامل بالزوج لغات بلا نشر (حمّلو من Artifacts وشوفو) |
| `full` | كلش + نشر (هذا اللي يخدم وحدو كل يوم 11:17 UTC) |

---

## ⚠️ حوايج لازم تعرفهم
- **YouTube quota:** 10,000/يوم، كل رفع = 1,600. الافتراضي: طويل + شورت واحد لكل لغة = 6,400 ✅. باقي الشورتس يروحو لـ TikTok/IG/FB.
- **قصص أشخاص حقيقيين:** السيستام يكتب من Wikipedia ويطلب من الـ AI ما يخترعش، وما يحكيش إشاعات على أنها حقائق. السكريبت يتراجع زوج مرات، ومنها مرة تدقيق في الحقائق. لكن الغلط يقدر يصرا، والقناة قناتك أنت. **نصيحتي:** في الأسابيع الأولى استعمل `no-publish` وشوف الفيديوهات قبل ما تخليه `full`.
- **سياسة يوتيوب (inauthentic content):** المحتوى الآلي المكرر يقدر يتحرم من الربح. صوتك + قصص ترند + مونتاج متنوع يقللو الخطر بزاف.
- **الوقت:** بـ Chatterbox على CPU كل لغة تاخذ ~2-3 ساعات (صوت + مونتاج)، والحد في GitHub هو 6 ساعات. إذا قربت تفوتو: نقّص `target_minutes`، ولا استعمل ElevenLabs.

## هيكل المشروع
```
config.yaml            كل الإعدادات
run.py                 التشغيل (stages: write / produce / finalize)
engine/trends.py       شكون ترند اليوم
engine/people.py       بحث Wikipedia + صور Commons + قص الخلفية للثمبنيل
engine/writer.py       الموضوع، السكريبت، المراجعة، الإسبانية، الشورتس، العناوين
engine/tts.py          صوتك (Chatterbox / ElevenLabs / Edge)
engine/align.py        توقيت كل كلمة (faster-whisper)
engine/media.py        لقطات Pexels / Pixabay
engine/render.py       يحضّر props ويشغّل Remotion
engine/uploaders/      YouTube, TikTok, Instagram/Facebook
video/                 مشروع Remotion
```
