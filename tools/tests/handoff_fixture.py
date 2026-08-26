"""One doctrine-valid story fixture, shared by every workflow test.

Handoff §7 fixed the book at 22 interior pages plus two separate covers, so a
test story is only a realistic test if it has that shape. Building it in one
place keeps the suites from drifting apart — and from quietly re-encoding the
old 20-page assumption.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doctrine = _load("doctrine")

HERO_NAME = "أحمد"
HERO_ID = "persona-01"
SCHOOL = "school-yard"
GRANDMA = "grandma-house"

PDF_PAGE_COUNT = doctrine.doctrine_pdf_page_count()
STORY_PAGE_COUNT = doctrine.doctrine_story_page_count()

# page-02 … page-21: (text, beat, locationId). The two grandma pages carry a
# visible movement bridge in their own text, which is what the spine check reads.
_STORY_PAGES: list[tuple[str, str, str]] = [
    ("قبل الفصل، أحمد مسك كورة الإسفنج الزرقا في إيده.", "أحمد يستعد قبل الفصل", SCHOOL),
    ("الفصل اتملى، وأحمد قعد في الصف الأخير جنب الشباك.", "أحمد ياخد مكانه في الفصل", SCHOOL),
    ("الأستاذ قال إن كل واحد هيحكي حكاية قدام الفصل.", "الأستاذ يعلن مهمة الحكي", SCHOOL),
    ("قلب أحمد دق بسرعة لما سمع اسمه في الليستة.", "التوتر يبدأ قبل دوره", SCHOOL),
    ("أحمد حب يحكي حكايته من غير ما صوته يرتعش.", "أحمد يحدد اللي عايزه", SCHOOL),
    ("جرب يتكلم مرة، فطلع صوته واطي قوي.", "محاولة أولى مش ناجحة", SCHOOL),
    ("جرب تاني وهو ماسك الكورة، فإيده اتهزت.", "محاولة تانية لسه صعبة", SCHOOL),
    ("بعد المدرسة، أحمد راح بيت جدته في إسكندرية.", "نقلة لبيت جدته", GRANDMA),
    ("جدته حكتله إنها بتعد لتلاتة قبل ما تتكلم.", "جدته تدي تقنية عملية واحدة", GRANDMA),
    ("بعد الزيارة، أحمد رجع البيت وهو بيعد لتلاتة.", "رجوع من عند جدته بالتقنية", SCHOOL),
    ("جرب يعد لتلاتة قدام المراية، وصوته طلع أوضح.", "تجربة التقنية في البيت", SCHOOL),
    ("تاني يوم، أحمد دخل الفصل والكورة في شنطته.", "يوم جديد في المدرسة", SCHOOL),
    ("سمع اسمه، فحس بنفس التوتر القديم في بطنه.", "التوتر بيرجع قبل الدور", SCHOOL),
    ("صاحبه لاحظ إيده بتترعش وقاله شكلك متوتر.", "صاحبه يلاحظ علامة خارجية", SCHOOL),
    ("أحمد قال لنفسه هعد لتلاتة قبل ما أبدأ كلامي.", "أحمد ياخد قراره بنفسه", SCHOOL),
    ("وقف قدام الفصل، عد واحد اتنين تلاتة، وبدأ يحكي.", "أحمد ينفذ قراره قدام الفصل", SCHOOL),
    ("حكى حكايته للآخر، وصحابه سمعوه من غير مقاطعة.", "الحكاية بتخلص كاملة", SCHOOL),
    ("الأستاذ قاله صوتك وصل لآخر الفصل النهارده.", "اعتراف بالنتيجة من الأستاذ", SCHOOL),
    ("صحابه لفوا حواليه وطلبوا يسمعوا حكاية تانية.", "الأصحاب بيطلبوا كمان", SCHOOL),
    ("أحمد حط الكورة في شنطته عشان يستعملها بكرة.", "أحمد بيثبت العادة الجديدة", SCHOOL),
]

_LOCATIONS = [
    {
        "id": SCHOOL,
        "nameAr": "فناء المدرسة",
        "visualDefinition": (
            "A wide school yard with cream plaster walls, a green painted iron "
            "gate, four tall ficus trees along the east wall, grey concrete "
            "tiles, a red-and-white four-square court, and a low blue bench "
            "under the arcade."
        ),
        "pageCue": "the cream yard with the green gate and the blue bench",
    },
    {
        "id": GRANDMA,
        "nameAr": "بيت جدته في إسكندرية",
        "visualDefinition": (
            "A first-floor Alexandria flat with a wooden balcony over a "
            "sea-facing street, teal shutters, a round brass tea tray on a "
            "carved side table, faded rose wallpaper, and a tall bookcase with "
            "glass doors beside the balcony arch."
        ),
        "pageCue": "the teal-shuttered balcony over the sea street",
    },
]


def story_page_ids() -> list[str]:
    return doctrine.structure_slots(PDF_PAGE_COUNT)["storyPages"]


def build_handoff_story(**overrides: Any) -> dict[str, Any]:
    """A complete `hekayati-22` story that passes review-story cleanly."""
    slots = doctrine.structure_slots(PDF_PAGE_COUNT)
    ids = slots["storyPages"]
    assert len(ids) == len(_STORY_PAGES) == STORY_PAGE_COUNT

    pages: list[dict[str, Any]] = [
        {
            "id": "cover",
            "role": "cover",
            "text": "أحمد وخطوته الهادية",
            "beat": "عنوان يوعد برحلة هادية",
            "participants": [HERO_ID],
            "guests": [],
            "locationId": SCHOOL,
            "setting": "فناء المدرسة الصبح",
            "action": "أحمد واقف ماسك كورة إسفنج زرقا",
        },
        doctrine.dedication_page(HERO_NAME, SCHOOL),
    ]
    previous_location = SCHOOL
    for page_id, (text, beat, location) in zip(ids, _STORY_PAGES):
        page: dict[str, Any] = {
            "id": page_id,
            "role": "story",
            "text": text,
            "beat": beat,
            "participants": [HERO_ID],
            "guests": [],
            "locationId": location,
            "setting": "مكان",
            "action": beat,
        }
        if location != previous_location:
            page["transitionFromPrevious"] = text
        previous_location = location
        pages.append(page)

    pages.append(doctrine.other_stories_page(slots["otherStories"], SCHOOL))
    pages.append(
        {
            "id": "back-cover",
            "role": "back-cover",
            "text": doctrine.back_cover_text(),
            "beat": "دعوة تسويقية للأهل على ضهر الكتاب",
            "participants": [],
            "guests": [],
            "locationId": SCHOOL,
            "setting": "خلفية هادية من عالم القصة",
            "action": "صفحة نص تسويقي وخمس أيقونات، من غير شخصيات",
            "fixedByDoctrine": True,
        }
    )

    story: dict[str, Any] = {
        "title": "قصة أحمد",
        "targetAge": 5,
        "languageProfileId": "age-3-5",
        "language": "natural Egyptian Arabic",
        "themeId": "storybook",
        "visualStyle": "premium whimsical children's storybook digital illustration",
        "purpose": "habit",
        "storyType": "B",
        "bookStructure": doctrine.BOOK_STRUCTURE_ID,
        "storyGoal": {
            "mode": "educational",
            "goalAr": "يمسك كورة الإسفنج ويعد لتلاتة",
            "updatedAt": "2026-08-25T00:00:00+00:00",
        },
        "pageCount": PDF_PAGE_COUNT,
        "outline": "أحمد بيتعلم يهدّي نفسه قبل ما يتكلم قدام الفصل",
        "personas": [
            {
                "id": HERO_ID,
                "displayName": HERO_NAME,
                "role": "hero",
                "fixedOutfit": "تيشرت أخضر وبنطلون جينز",
            }
        ],
        "guestCharacters": [],
        "locations": copy.deepcopy(_LOCATIONS),
        "continuity": {
            "recurringProps": ["دبدوبه البني", "كورة إسفنج زرقاء"],
            "palette": "teal, sand, warm gold",
            "avoid": [],
        },
        "narrativeArc": {
            "setup": ids[0:2],
            "disruption": ids[2:4],
            "goal": ids[4:5],
            "attempts": ids[5:11],
            "clue": ids[11:14],
            "choice": ids[14:15],
            "decisiveAction": ids[15:17],
            "payoff": ids[17:19],
            "resolution": [ids[19], "back-cover"],
        },
        "pages": pages,
    }
    story.update(overrides)
    return story


def page_by_id(story: dict[str, Any], page_id: str) -> dict[str, Any]:
    return next(page for page in story["pages"] if page["id"] == page_id)
