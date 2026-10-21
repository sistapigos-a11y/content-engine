"""Topic selection, research-grounded scripting, ES adaptation, shorts and metadata."""
import json
import random

from . import people, trends
from .llm import LLM
from .util import log

WORDS_PER_MIN = 140

SCENE_SCHEMA = ('{"narration":str,"type":"broll"|"photo"|"text"|"quote",'
                '"query":str,"person":str|null,"onscreen":str|null}')

SCENE_RULES = (
    "Each scene = 2-4 sentences of narration plus ONE visual:\n"
    '- "photo": a real photo of a person; set "person" to their exact Wikipedia name.\n'
    '- "broll": stock footage; "query" = concrete filmable English words ("stadium night crowd", '
    '"teenager training football street"), never names of real people.\n'
    '- "text": big animated on-screen text, max 5 words, e.g. a number, date or key phrase ("16 YEARS OLD").\n'
    '- "quote": a REAL documented quote in "onscreen" and who said it in "person". Never invent quotes.\n'
    'Always fill "query" (used as fallback footage). Mix types: roughly 45% photo when the story is about '
    "people, 35% broll, 15% text, 5% quote. Never 3 identical types in a row.")


def _system(cfg, fmt):
    ch = cfg["channel"]
    f = ch["formats"][fmt]
    return (f"You are the head writer of a faceless YouTube documentary channel.\n"
            f"Format: {f['description']}\nAudience: {ch['audience']}\nTone: {ch['tone']}\n"
            "Rules: only verifiable facts, prefer facts from the RESEARCH text when given; say 'reportedly' "
            "for anything not confirmed; never invent quotes, dates, numbers or names; about real living "
            "people: no rumours presented as fact, no claims about crimes, health or private life unless "
            "documented by major outlets, stay respectful. No filler ('in this video', 'smash that like'). "
            "Write for the ear: short sentences, concrete images, open loops that pay off.")


def pick_format(cfg) -> str:
    fmts = {k: v for k, v in cfg["channel"]["formats"].items() if v.get("weight", 0) > 0}
    return random.choices(list(fmts), weights=[v["weight"] for v in fmts.values()])[0]


def pick_topic(llm: LLM, cfg: dict, history: list[str]) -> dict:
    fmt = pick_format(cfg)
    recent = "\n".join(f"- {t}" for t in history[-200:]) or "(none yet)"
    if fmt == "trending_person":
        signals = trends.collect(cfg)
        trend_text = "\n".join(
            f"- {s['title']} ({s['source']}, {s.get('views') or s.get('traffic') or ''}) {s.get('news') or ''}"
            for s in signals[:250]) or "(trend feeds unavailable: use people you know are hot right now)"
        idea = llm.json(
            "These are today's trend signals (most viewed Wikipedia pages and Google Trends):\n"
            f"{trend_text}\n\nPick the 5 best PEOPLE for a story video in the style of channels like "
            "'Nobody Believed', 'X Warned Us 3 Years Ago', 'X Was Right All Along', 'The Rise of X', "
            "'How X Fooled Everyone'. Favour: footballers, athletes, streamers, YouTubers, rappers, "
            "influencers, viral internet figures that are trending NOW and have a real arc "
            "(doubted -> proved right, rise, comeback, fall, rivalry). They need an English Wikipedia page. "
            "A second person (mentor, rival, doubter) makes the thumbnail stronger.\n"
            f"Avoid repeating these past topics:\n{recent}\n\n"
            '{"ideas":[{"topic":str,"angle":str,"hook_title":str,"main_person":str,'
            '"secondary_person":str|null,"wikipedia_title":str,"why_now":str,"virality":1-10}]}',
            _system(cfg, fmt))["ideas"]
        idea.sort(key=lambda i: i.get("virality", 0), reverse=True)
        chosen = idea[0]
    else:
        ideas = llm.json(
            "Propose 10 documentary topics for this format that would perform well on YouTube in both "
            f"English and Spanish markets. Avoid anything close to these past topics:\n{recent}\n\n"
            '{"ideas":[{"topic":str,"angle":str,"hook_title":str,"wikipedia_title":str,'
            '"main_person":str|null,"secondary_person":str|null,"virality":1-10,"fact_density":1-10}]}',
            _system(cfg, fmt))["ideas"]
        ideas.sort(key=lambda i: i.get("virality", 0) + i.get("fact_density", 0), reverse=True)
        chosen = ideas[0]
    chosen["format"] = fmt
    log.info("Picked [%s]: %s", fmt, chosen["topic"])
    return chosen


def gather_research(idea: dict) -> str:
    parts = []
    for title in {idea.get("wikipedia_title"), idea.get("main_person"), idea.get("secondary_person")} - {None, ""}:
        text = people.research(title)
        if text:
            parts.append(f"### {title}\n{text[:20000]}")
    return "\n\n".join(parts)[:45000]


def write_long_script(llm: LLM, cfg: dict, idea: dict, research: str) -> dict:
    lv = cfg["long_video"]
    n = lv["sections"]
    words_per_section = int(lv["target_minutes"] * WORDS_PER_MIN / n)
    sys = _system(cfg, idea["format"])
    brief = f"Topic: {idea['topic']}\nAngle: {idea['angle']}\nWorking title: {idea.get('hook_title')}\n"
    res = f"\nRESEARCH (ground truth, use it):\n{research}\n" if research else ""

    outline = llm.json(
        f"{brief}{res}\nBuild a {n}-chapter outline for a {lv['target_minutes']}-minute documentary. "
        "Chapter 1 is a cold open: start on the most gripping moment, then promise the payoff. "
        "Each chapter ends on a question or reveal that pulls into the next. The last chapter pays off "
        "the title's promise and leaves a lingering thought.\n"
        '{"chapters":[{"title":str,"beats":[str],"ends_with":str}]}', sys)

    sections, story_so_far = [], ""
    for i, ch in enumerate(outline["chapters"], 1):
        log.info("Writing chapter %d/%d: %s", i, n, ch["title"])
        sec = llm.json(
            f"{brief}Outline: {json.dumps(outline['chapters'], ensure_ascii=False)}\n{res[:25000]}\n"
            f"Story so far (end): ...{story_so_far[-1500:]}\n\n"
            f"Write chapter {i}: '{ch['title']}' covering {ch['beats']} and ending with: {ch['ends_with']}.\n"
            f"About {words_per_section} words of narration.\n{SCENE_RULES}\n"
            f'{{"scenes":[{SCENE_SCHEMA}]}}', sys)
        sections.append({"title": ch["title"], "scenes": sec["scenes"]})
        story_so_far += " ".join(s["narration"] for s in sec["scenes"])

    return {"topic": idea["topic"], "angle": idea["angle"], "format": idea["format"], "sections": sections}


def review_script(llm: LLM, cfg: dict, script: dict, research: str) -> dict:
    text = "\n\n".join(f"## {s['title']}\n" + " ".join(x["narration"] for x in s["scenes"])
                       for s in script["sections"])
    return llm.json(
        "Act as a strict YouTube documentary editor AND fact-checker. Score 1-10 on: hook strength, "
        "retention/pacing, factual accuracy versus the research, originality (no generic AI filler). "
        "List claims that are not supported by the research.\n\n"
        f"RESEARCH:\n{research[:20000]}\n\nSCRIPT:\n{text[:50000]}\n\n"
        '{"overall":number,"fixes":[str],"factual_risks":[str]}', _system(cfg, script["format"]))


def improve_script(llm: LLM, cfg: dict, script: dict, review: dict) -> dict:
    notes = review.get("fixes", []) + [f"Unsupported claim, remove or soften: {r}" for r in review.get("factual_risks", [])]
    out = []
    for sec in script["sections"]:
        out.append(llm.json(
            f"Editor notes for the whole documentary: {notes}\n\nRewrite this chapter applying the notes "
            f"that concern it. Keep similar length and the same scene format.\n{SCENE_RULES}\n"
            f"{json.dumps(sec, ensure_ascii=False)}\n"
            f'{{"title":str,"scenes":[{SCENE_SCHEMA}]}}', _system(cfg, script["format"])))
    return {**script, "sections": out}


def adapt_to_spanish(llm: LLM, cfg: dict, script: dict) -> dict:
    """Meaning-based adaptation (not word-for-word) for a native Spanish voiceover."""
    out = []
    for sec in script["sections"]:
        out.append(llm.json(
            "Adapt this documentary chapter into natural, neutral Latin-American Spanish for voiceover. "
            "Translate meaning, rhythm and suspense, not words. Keep names, dates and numbers exact. "
            "Translate 'narration', 'title' and 'onscreen' (quotes: use the established Spanish version or "
            "translate faithfully). Keep 'type', 'query' and 'person' unchanged.\n"
            f"{json.dumps(sec, ensure_ascii=False)}\n"
            f'{{"title":str,"scenes":[{SCENE_SCHEMA}]}}', _system(cfg, script["format"])))
    return {**script, "sections": out}


def write_metadata(llm: LLM, cfg: dict, script: dict, idea: dict, lang: str) -> dict:
    language = {"en": "English", "es": "Spanish"}[lang]
    intro = " ".join(s["narration"] for s in script["sections"][0]["scenes"])[:2000]
    chapters = [s["title"] for s in script["sections"]]
    return llm.json(
        f"Write YouTube metadata in {language} for: {script['topic']} (working title: {idea.get('hook_title')}).\n"
        f"Opening: {intro}\nChapters: {chapters}\n"
        "Title: curiosity-driven like 'Xavi Warned Us 3 Years Ago' or 'IShowSpeed Was Right All Along', "
        "<= 60 chars, true to the video, no ALL CAPS. Description: 2 compelling paragraphs. 15 tags. "
        "Thumbnail: two short punchy words that frame the person, one on each side "
        "(e.g. NOBODY / BELIEVED, THEY / LAUGHED, TOO / LATE), in "
        f"{language}, each max 9 letters.\n"
        '{"title":str,"description":str,"tags":[str],"thumb_left":str,"thumb_right":str}',
        _system(cfg, script["format"]))


def write_shorts(llm: LLM, cfg: dict, script: dict, lang: str) -> list[dict]:
    sc = cfg["shorts"]
    language = {"en": "English", "es": "Spanish"}[lang]
    full = json.dumps(script["sections"], ensure_ascii=False)[:60000]
    words = int(sc["max_seconds"] * 2.4)
    data = llm.json(
        f"From this documentary, create {sc['per_video']} standalone vertical Shorts in {language}. "
        "Each picks ONE surprising moment, opens with a scroll-stopping first line (no intro), "
        f"max {words} words, scenes of 1-2 sentences, and ends with a twist or a line that makes people "
        f"want the full story.\n{SCENE_RULES}\n\n{full}\n\n"
        f'{{"shorts":[{{"title":str,"caption":str,"hashtags":[str],"scenes":[{SCENE_SCHEMA}]}}]}}',
        _system(cfg, script["format"]))
    return data["shorts"][: sc["per_video"]]
