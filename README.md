# 🎬 بوت أفلام VOX و Premiere

بوت تيليجرام بيشيك على [elCinema](https://elcinema.com/en/now/eg) كذا مرة في اليوم. أول ما فيلم جديد ينزل في سينمات **VOX** أو **Premiere**، بيبعتلك:

- **البوستر** واسم الفيلم وتاريخ نزوله
- **الفروع** اللي بيتعرض فيها (مثلاً VOX: Mall of Egypt · City Centre Almaza)
- لينكات elCinema وموقع VOX وموقع Premiere

> موقع VOX بيمنع البرامج الآلية، وموقع Premiere بيرفض سيرفرات GitHub. عشان كده كل البيانات بتيجي من elCinema، وهو بيعرض كل فروع السلسلتين.

### إمتى بيبعت
- **فيلم جديد وصل VOX أو Premiere**: رسالة بالبوستر.
- **فيلم معروض في سينمات تانية بس**: مش بيبعت. لكن بيفضل يشيك عليه، ولو وصل VOX أو Premiere بعدين بيبعتلك.
- **أول تشغيل**: بيسجل الأفلام الموجودة من غير ما يبعتها، ويبعت رسالة واحدة إنه شغال.
- **لو elCinema وقع**: بيبعت تحذير مرة واحدة، ويقولك لما يرجع.

## التشغيل
بيشتغل لوحده على **GitHub Actions** (ملف `.github/workflows/check.yml`). المفروض كل ساعة، بس GitHub بيأخره، فعملياً بيشتغل كل كام ساعة. وبيحفظ اللي شافه في `data/state.json`.

محتاج الـ Secrets دي في **Settings ← Secrets and variables ← Actions**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

وعشان تشغله بإيدك: **Actions ← Check cinemas ← Run workflow**.

### على الجهاز
```bash
python3 -m venv .venv
```
```bash
.venv/bin/pip install -r requirements.txt
```
حط التوكن والـ chat id في `.env` (انسخ `.env.example`). لو مش عارف الـ chat id، ابعت `/start` للبوت وشغّل `.venv/bin/python get_chat_id.py`.

| الأمر | بيعمل إيه |
|---|---|
| `.venv/bin/python -m cinema_bot.main --dry-run` | يطبع الرسايل بدل ما يبعتها، ومش بيحفظ حاجة |
| `.venv/bin/python -m cinema_bot.main` | تشغيل حقيقي |
| `.venv/bin/python -m pytest` | الاختبارات |

## الإعدادات (`config.yaml`)
`chains`: السلاسل اللي يهمك تعرف لما فيلم يوصلها. كل سلسلة بتتعرف من كلمة في اسم السينما على elCinema. ممكن تضيف سلسلة زي Galaxy كده:
```yaml
  galaxy:
    title: Galaxy
    match: ["galaxy", "scene"]
    link: https://scenecinemas.com
```

عايز البوت يبعت فيلم معين تاني؟ امسحه من `known` في `data/state.json`.
