# التقرير العلمي والهندسي — Scientific &amp; Engineering Report

`Mishkaat_Engineering_Report.pdf` — التقرير الكامل للمشروع بالإنجليزية، 114 صفحة،
17 فصلاً وأربعة ملاحق.

The full technical, architectural and scientific documentation of Mishkaat: the
problem domain and the solution, the delimited scope, the six user classes and the
scope model, the functional and non-functional requirements, the architecture and
technology stack, the complete data dictionary and relationship model, the API
surface, the mathematics of the analytical engine, the security architecture, the
business workflows, the user interface, verification, deployment, and the system's
measured limitations.

## ما في المجلّد

```
docs/report/
├── Mishkaat_Engineering_Report.pdf   ← التقرير (الناتج النهائي)
├── build.py                          ← أداة التوليد
├── README.md
└── parts/                            ← مصدر التقرير: 15 ملفّ HTML
    ├── 00-head.html                  ← الأنماط وإعداد الطباعة
    ├── 01-front.html                 ← الغلاف، والملخّص، والفهرس
    ├── 02-ch1-2.html … 14-appendices.html
```

المصدر مقسَّمٌ إلى أجزاء مرقّمة لا ملفّاً واحداً: التعديل على فصلٍ لا يمرّ على
غيره، وترتيب الدمج هو ترتيب أسماء الملفّات.

## إعادة التوليد

```bash
pip install playwright pypdfium2     # المتصفّح نفسه غير مطلوب تنزيله إن كان مثبَّتاً
python docs/report/build.py
```

يعمل السكربت على مرحلتين: يرسم الوثيقة أوّلاً ليعرف رقم الصفحة التي يبدأ عندها
كلُّ فصل، ثمّ يكتب الأرقام في الفهرس ويرسمها ثانيةً. وطول الفهرس لا يتغيّر بين
المرحلتين، فتبقى الأرقام صحيحة.

يُبحَث عن Chromium في `$CHROMIUM_PATH`، ثمّ `/opt/pw-browsers/chromium`، ثمّ في
المسار الافتراضي لـ Playwright.

`mishkaat-report.html` ملفٌّ مُولَّد من `parts/` ولا يُودَع في المستودع — عدِّل
الأجزاء لا هو.

## Contents at a glance

| Ch. | Title |
|----|---|
| 1 | Introduction — problem statement, aim and objectives, contributions |
| 2 | Scope, assumptions and delimitations |
| 3 | Stakeholders and users — roles, scope model, capability matrix |
| 4 | Requirements specification — 74 FR, 18 NFR, 22 business rules, use cases |
| 5 | System architecture |
| 6 | Technology stack |
| 7 | Database design and full data dictionary — 28 collections, 71 indexes |
| 8 | API specification — all 136 endpoints |
| 9 | The analytical engine — metrics, forecasting, gamification |
| 10 | Security engineering — threat model and controls |
| 11 | Business workflows |
| 12 | User interface and interaction design |
| 13 | Verification and quality assurance |
| 14 | Deployment and operations |
| 15 | Project metrics and development history |
| 16 | Evaluation, limitations and future work |
| 17 | Conclusion |
| A–D | Environment variables · audit actions · endpoint index · glossary |
