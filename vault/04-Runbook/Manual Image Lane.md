---
title: "Manual Image Lane"
tags: [images, runbook]
generated: true
generated_by: hekayati-generated
doctrine_version: "2026-08-26"
---

> [!info] ملف متولّد
> الملف ده بيتكتب من `tools/references/handoff/doctrine.json`. لو عايز تغيّر قاعدة، غيّرها في الدكترين وشغّل `build-vault` تاني — أي تعديل يدوي هنا هيتمسح.


# اللاين اليدوي لتوليد الصور

الأداة: أداة ChatGPT على الموبايل — يدوية، بدون ذاكرة حالة. مالهاش ذاكرة — كل رسالة لازم تبقى كاملة بذاتها.

## القواعد اللي بتحكم كل رسالة

- صفحة واحدة بس في كل رد (`maxPagesPerMessage = 1`)
- ملف الدفعة فيه صفحتين بحد أقصى (`maxPagesPerFile = 2`)
- الاتجاه: landscape 16:9 دايمًا
- الـReference Sheet مرفق في كل رسالة، والصور المولّدة قبل كده ممنوعة كمرجع
- مشهد واحد = صورة واحدة، من غير تقسيم لقطات

## توليد الملفات

```bash
# صفحة واحدة على الشاشة
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project $CLIENT --asset page-05

# دفعة صفحتين لملف Markdown جوه الفولت
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project $CLIENT --asset page-05 --asset page-06 \
  --out $CLIENT/output/manual

# كل الكتاب، ملف لكل دفعة صفحتين
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project $CLIENT --all --out $CLIENT/output/manual
```

الملفات بتتكتب في `output/manual/` جوه فولت العميل، فتقدر تفتحها على الموبايل وتنسخ الرسالة زي ما هي.

## ترتيب التوليد

1. شيت البطل (4 زوايا، لوحده)
2. شيت الشخصيات المساندة (كلهم في شيت واحد، 4 زوايا)
3. صفحات الأماكن
4. صفحات القصة بالترتيب
5. **الأغلفة في الآخر** عشان تطلع شبه الفن النهائي

→ [[قواعد أداة الصور]]
