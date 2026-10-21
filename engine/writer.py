"""Topic selection, long-form scripting, ES adaptation, shorts and metadata."""
from .llm import LLM
from .util import log

WORDS_PER_MIN = 140


def _system(cfg):
    ch = cfg["channel"]
    return (f"You are the head writer of a faceless YouTube documentary channel.\n"
            f"Niche: {ch['niche']}\nAudience: {ch['audience']}\nTone: {ch['tone']}\n"
            "Rules: only verifiable facts; when something is disputed say so; never invent quotes, "
            "dates or names; no filler like 'in this video' or 'don't forget to subscribe' mid-story; "
            "write for the ear: short sentences, concrete images, open loops that pay off.")


def pick_topic(llm: LLM, cfg: dict, history: list[str]) -> dict:
    recent = "\n".join(f"- {t}" for t in history[-200:]) or "(none yet)"
    ideas = llm.json(
        f"Propose 10 documentary topics for this channel that would perform well on YouTube in both "
        f"English and Spanish-speaking markets. Avoid anything too close to these past topics:\n{recent}\n\n"
        'JSON: {"ideas":[{"topic":str,"angle":str,"why_it_clicks":str,"virality":1-10,"fact_density":1-10}]}',
        _system(cfg))["ideas"]
    ideas.sort(key=lambda i: i.get("virality", 0) + i.get("fact_density", 0), reverse=True)
    log.info("Picked topic: %s", ideas[0]["topic"])
    return ideas[0]


def write_long_script(llm: LLM, cfg: dict, idea: dict) -> dict:
    lv = cfg["long_video"]
    n = lv["sections"]
    words_per_section = int(lv["target_minutes"] * WORDS_PER_MIN / n)
    sys = _system(cfg)

    outline = llm.json(
        f"Topic: {idea['topic']}\nAngle: {idea['angle']}\n\n"
        f"Build a {n}-chapter outline for a {lv['target_minutes']}-minute documentary. "
        "Chapter 1 opens with a cold-open hook (the most gripping moment) before any context. "
        "Each chapter ends on a question or reveal that pulls into the next. Last chapter resolves "
        "and leaves a lingering thought.\n"
        'JSON: {"title_working":str,"chapters":[{"title":str,"beats":[str],"ends_with":str}]}', sys)

    sections, story_so_far = [], ""
    for i, ch in enumerate(outline["chapters"], 1):
        log.info("Writing chapter %d/%d: %s", i, n, ch["title"])
        sec = llm.json(
            f"Documentary: {idea['topic']}\nFull outline: {outline}\n\n"
            f"Story so far (last part): ...{story_so_far[-1500:]}\n\n"
            f"Write chapter {i}: '{ch['title']}' covering beats {ch['beats']} and ending with: {ch['ends_with']}.\n"
            f"About {words_per_section} words of narration, split into scenes of 2-4 sentences. "
            "For each scene give a short stock-footage search query in English (concrete, filmable "
            "nouns: 'old lighthouse storm', not 'mystery').\n"
            'JSON: {"scenes":[{"narration":str,"visual":str}]}', sys)
        sections.append({"title": ch["title"], "scenes": sec["scenes"]})
        story_so_far += " ".join(s["narration"] for s in sec["scenes"])

    return {"topic": idea["topic"], "angle": idea["angle"], "sections": sections}


def review_script(llm: LLM, cfg: dict, script: dict) -> dict:
    text = "\n\n".join(f"## {s['title']}\n" + " ".join(x["narration"] for x in s["scenes"])
                       for s in script["sections"])
    return llm.json(
        "Act as a strict YouTube documentary editor. Score this script 1-10 on: hook strength, "
        "retention/pacing, factual caution, originality (not generic AI filler). Give an overall score "
        "and up to 5 concrete fixes.\n\n" + text[:60000] +
        '\n\nJSON: {"overall":number,"scores":{},"fixes":[str],"factual_risks":[str]}',
        _system(cfg))


def improve_script(llm: LLM, cfg: dict, script: dict, review: dict) -> dict:
    fixes = review.get("fixes", []) + [f"Fact risk: {r}" for r in review.get("factual_risks", [])]
    out = []
    for sec in script["sections"]:
        new = llm.json(
            f"Editor notes for the whole documentary: {fixes}\n\nRewrite this chapter applying the "
            "notes that concern it. Keep the same JSON shape and similar length.\n"
            f"{ {'title': sec['title'], 'scenes': sec['scenes']} }\n"
            'JSON: {"title":str,"scenes":[{"narration":str,"visual":str}]}', _system(cfg))
        out.append(new)
    return {**script, "sections": out}


def adapt_to_spanish(llm: LLM, cfg: dict, script: dict) -> dict:
    """Meaning-based adaptation (not word-for-word) for a native Spanish voiceover."""
    out = []
    for sec in script["sections"]:
        new = llm.json(
            "Adapt this documentary chapter into natural, neutral Latin-American Spanish for voiceover. "
            "Translate meaning, rhythm and suspense, not words. Keep names/dates exact. Keep the "
            "'visual' field in English unchanged.\n"
            f"{ {'title': sec['title'], 'scenes': sec['scenes']} }\n"
            'JSON: {"title":str,"scenes":[{"narration":str,"visual":str}]}', _system(cfg))
        out.append(new)
    return {**script, "sections": out}


def write_metadata(llm: LLM, cfg: dict, script: dict, lang: str) -> dict:
    language = {"en": "English", "es": "Spanish"}[lang]
    intro = " ".join(s["narration"] for s in script["sections"][0]["scenes"])[:2000]
    chapters = [s["title"] for s in script["sections"]]
    return llm.json(
        f"Write YouTube metadata in {language} for a documentary about: {script['topic']}.\n"
        f"Opening: {intro}\nChapters: {chapters}\n"
        "Title: curiosity-driven, <= 70 chars, no clickbait lies, no ALL CAPS. "
        "Description: 2 compelling paragraphs, then a 'Sources & notes' line saying facts were "
        "researched and AI tools assisted production. 15 tags. Thumbnail text: 2-4 punchy words.\n"
        'JSON: {"title":str,"description":str,"tags":[str],"thumbnail_text":str}', _system(cfg))


def write_shorts(llm: LLM, cfg: dict, script: dict, lang: str) -> list[dict]:
    sc = cfg["shorts"]
    language = {"en": "English", "es": "Spanish"}[lang]
    full = " ".join(x["narration"] for s in script["sections"] for x in s["scenes"])[:40000]
    words = int(sc["max_seconds"] * 2.4)
    data = llm.json(
        f"From this documentary, create {sc['per_video']} standalone vertical Shorts in {language}. "
        "Each picks ONE surprising moment, starts with a scroll-stopping first line (no intro), "
        f"max {words} words, ends with a twist or a line that makes people want the full video. "
        "Scenes of 1-2 sentences, with an English stock-footage query each.\n\n" + full +
        '\n\nJSON: {"shorts":[{"title":str,"caption":str,"hashtags":[str],'
        '"scenes":[{"narration":str,"visual":str}]}]}', _system(cfg))
    return data["shorts"][: sc["per_video"]]
