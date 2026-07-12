"""Sarvo Podcast Studio — Streamlit frontend for the pipeline.

Layout (dashboard-first, like a SaaS app):
  HOME    → big "Create New Video" button + a card gallery of every episode
            (each shows its thumbnail, stage and progress; click to resume).
  CREATE  → the topic form.
  EPISODE → the guided, step-locked wizard (Plan → … → Upload).

Run the backend first:   uv run uvicorn main:app --reload
Then this UI:            uv run streamlit run frontend/app.py
"""

import requests
import streamlit as st

API = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 900  # generation calls can take minutes

st.set_page_config(page_title="Sarvo Podcast Studio", page_icon="🎙️", layout="wide")

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.0rem; max-width: 1200px;}

    .topbar {display:flex; justify-content:space-between; align-items:center;
             padding: 4px 0 14px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 18px;}
    .brand {font-size: 1.5rem; font-weight: 800; color:#0F172A;}
    .backend {font-size:0.85rem; color:#64748B;}

    .pill {display:inline-block; padding: 2px 12px; border-radius: 999px;
           font-size: 0.78rem; font-weight: 600;}
    .pill-ok   {background:#DCFCE7; color:#166534;}
    .pill-run  {background:#FEF9C3; color:#854D0E;}
    .pill-fail {background:#FEE2E2; color:#991B1B;}
    .pill-idle {background:#E2E8F0; color:#334155;}

    .chip {display:inline-block; background:#F1F5F9; color:#334155;
           padding:3px 12px; border-radius:8px; margin-right:8px; font-size:0.85rem;}

    .steps {display:flex; gap:6px; margin: 10px 0 4px 0; flex-wrap:wrap;}
    .step {padding:5px 12px; border-radius:8px; font-size:0.82rem; font-weight:600;}
    .step-done {background:#DCFCE7; color:#166534;}
    .step-next {background:#DBEAFE; color:#1E40AF; outline:2px solid #93C5FD;}
    .step-lock {background:#F1F5F9; color:#94A3B8;}

    .card-title {font-weight:700; font-size:0.92rem; color:#0F172A;
                 line-height:1.25; height: 2.5em; overflow:hidden; margin: 6px 0 4px 0;}
    .card-ph {width:100%; aspect-ratio:16/9; border-radius:10px;
              background:linear-gradient(135deg,#0F766E,#14B8A6);
              display:flex; align-items:center; justify-content:center;
              color:white; font-size:2.2rem;}

    div.stButton > button {border-radius:10px;}
    div.stButton > button[kind="primary"] {font-weight:700;}
</style>
""", unsafe_allow_html=True)

SUGGESTED_TOPICS = [
    "What Old People Regret Most — Life Lessons in Simple English",
    "The 5-Second Habit That Changes a Boring Life",
    "Why Smart People Stay Poor | Easy English Podcast",
    "Stop Saying 'I'm Fine' — Phrases That Make You Sound Confident",
    "Morning Habits of Successful People | Real-Life Conversation",
]

STATUS_META = {
    "queued": ("Queued", "pill-idle"),
    "scripting": ("Writing script…", "pill-run"),
    "scripted": ("Script ready", "pill-run"),
    "audio_done": ("Audio ready", "pill-run"),
    "image_done": ("Image ready", "pill-run"),
    "video_done": ("Video ready", "pill-run"),
    "metadata_done": ("Packaged", "pill-run"),
    "uploaded": ("Uploaded", "pill-ok"),
    "failed": ("Failed", "pill-fail"),
}


# ---------------- API client ----------------

def api(method: str, path: str, json: dict | None = None, raw: bool = False):
    try:
        resp = requests.request(method, f"{API}{path}", json=json, timeout=TIMEOUT)
    except requests.ConnectionError:
        st.error("Backend is not running. Start it with:  `uv run uvicorn main:app --reload`")
        return None
    if resp.status_code >= 400:
        try:
            st.warning(resp.json().get("detail", resp.text))
        except Exception:
            st.warning(f"Error {resp.status_code}")
        return None
    return resp.content if raw else resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def cached_file(path: str, version: str) -> bytes | None:
    """Fetch a media file, cached by (path, updated_at) so cards stay fast."""
    try:
        resp = requests.get(f"{API}{path}", timeout=30)
        return resp.content if resp.status_code == 200 else None
    except requests.RequestException:
        return None


def backend_alive() -> dict | None:
    try:
        return requests.get(f"{API}/health", timeout=5).json()
    except Exception:
        return None


def goto(view: str) -> None:
    st.session_state["view"] = view
    st.rerun()


# ---------------- shared: top bar ----------------

def render_topbar(health: dict | None) -> None:
    status = (f"🟢 Backend connected · {health['episodes']} episodes"
              if health else "🔴 Backend offline — run: uv run uvicorn main:app --reload")
    st.markdown(
        f"<div class='topbar'><span class='brand'>🎙️ Sarvo Podcast Studio</span>"
        f"<span class='backend'>{status}</span></div>",
        unsafe_allow_html=True,
    )


# ---------------- home: create button + history gallery ----------------

def episode_progress(ep: dict) -> float:
    done = sum([ep["has_blueprint"], ep["has_script"], ep["has_audio"], ep["has_image"],
                ep["has_video"], ep["has_metadata"], bool(ep["youtube_video_id"])])
    return done / 7


def render_home() -> None:
    b1, b2 = st.columns(2)
    if b1.button("🎬  Create New Video", type="primary", use_container_width=True):
        goto("create")
    if b2.button("💼  Create LinkedIn Post", type="primary", use_container_width=True):
        goto("create_linkedin")

    # --- Video gallery ---
    st.markdown("### 🎬 Recent videos")
    episodes = api("GET", "/episodes") or []
    if not episodes:
        st.info("No videos yet — press **Create New Video** to make your first episode!")
    for row_start in range(0, len(episodes), 4):
        cols = st.columns(4)
        for col, ep in zip(cols, episodes[row_start:row_start + 4]):
            with col.container(border=True):
                thumb = None
                if ep["has_image"]:
                    thumb = cached_file(f"/episodes/{ep['id']}/thumbnail/file",
                                        ep["updated_at"])
                if thumb:
                    st.image(thumb, use_container_width=True)
                else:
                    st.markdown("<div class='card-ph'>🎙️</div>", unsafe_allow_html=True)
                short = ep["topic"][:64] + ("…" if len(ep["topic"]) > 64 else "")
                st.markdown(f"<div class='card-title'>{short}</div>", unsafe_allow_html=True)
                label, klass = STATUS_META.get(ep["status"], (ep["status"], "pill-idle"))
                st.markdown(f"<span class='pill {klass}'>{label}</span>", unsafe_allow_html=True)
                st.progress(episode_progress(ep))
                if st.button("Open →", key=f"open_{ep['id']}", use_container_width=True):
                    st.session_state["episode_id"] = ep["id"]
                    goto("episode")

    # --- LinkedIn gallery ---
    posts = api("GET", "/linkedin") or []
    if posts:
        st.markdown("### 💼 Recent LinkedIn posts")
        for row_start in range(0, len(posts), 4):
            cols = st.columns(4)
            for col, po in zip(cols, posts[row_start:row_start + 4]):
                with col.container(border=True):
                    img = None
                    if po["has_image"]:
                        img = cached_file(f"/linkedin/{po['id']}/image/file", po["updated_at"])
                    if img:
                        st.image(img, use_container_width=True)
                    else:
                        st.markdown("<div class='card-ph'>💼</div>", unsafe_allow_html=True)
                    short = po["brief"][:64] + ("…" if len(po["brief"]) > 64 else "")
                    st.markdown(f"<div class='card-title'>{short}</div>",
                                unsafe_allow_html=True)
                    done = "pill-ok" if po["has_image"] else "pill-run"
                    txt = "Ready" if po["has_image"] else (
                        "Caption ready" if po["has_caption"] else "Draft")
                    st.markdown(f"<span class='pill {done}'>{txt}</span>",
                                unsafe_allow_html=True)
                    if st.button("Open →", key=f"lopen_{po['id']}", use_container_width=True):
                        st.session_state["post_id"] = po["id"]
                        goto("linkedin")


# ---------------- create view ----------------

def render_create() -> None:
    if st.button("← Back"):
        goto("home")

    st.markdown("## What should this episode be about?")
    st.caption("Give a topic with a built-in hook — a secret, a mistake, a 'why' — "
               "and the AI strategist will do the rest.")

    if "topic_draft" not in st.session_state:
        st.session_state["topic_draft"] = ""

    pick = st.pills("Need inspiration?", SUGGESTED_TOPICS, key="topic_pick")
    if pick and st.session_state.get("_last_pick") != pick:
        st.session_state["topic_draft"] = pick  # apply once, keep user edits after
        st.session_state["_last_pick"] = pick

    topic = st.text_area("Episode topic", key="topic_draft", height=90,
                         placeholder="e.g. Why Smart People Stay Poor | Easy English Podcast")

    context = st.text_area(
        "Your knowledge about this topic (optional)",
        key="context_draft", height=170,
        placeholder=("Know this topic well? Paste your notes, facts, examples or "
                     "explanations here — the AI will build the episode from YOUR "
                     "knowledge instead of only its own.\n\ne.g. for RAG: 'RAG = "
                     "Retrieval-Augmented Generation. The three steps are indexing, "
                     "retrieval, generation. Common mistake: chunk sizes too big…'"),
    )
    st.caption("💡 Leave it empty and the AI uses its general knowledge.")

    col1, col2 = st.columns([2, 1])
    minutes = col1.slider("Video length (minutes)", 1.0, 30.0, 5.0, 0.5)
    col2.markdown("<br>", unsafe_allow_html=True)
    create = col2.button("🚀 Create episode", type="primary", use_container_width=True,
                         disabled=not topic.strip())
    if minutes > 15:
        col1.caption("⚠️ Over 15 min needs a YouTube channel with 'Intermediate "
                     "features' enabled (youtube.com/features), or the upload gets "
                     "removed. Keep it ≤15 min until that's active.")

    if create and topic.strip():
        ep = api("POST", "/episodes", {
            "topic": topic.strip(),
            "duration_minutes": minutes,
            "context": context.strip() or None,
        })
        if ep:
            st.session_state["episode_id"] = ep["id"]
            goto("episode")


# ---------------- LinkedIn: create + wizard ----------------

def render_create_linkedin() -> None:
    if st.button("← Back"):
        goto("home")

    st.markdown("## 💼 New LinkedIn post")
    st.caption("Step 1 is the caption. Tell the AI what you want the post to be about — "
               "an AI update, a tip, a hot take, a tool you tried.")
    brief = st.text_area(
        "What should this post be about?", height=150,
        placeholder="e.g. Explain what MCP (Model Context Protocol) is and why it matters "
                    "for AI agents — make it simple and exciting for non-technical people.",
    )
    if st.button("✍️ Create & write caption", type="primary", disabled=not brief.strip()):
        post = api("POST", "/linkedin", {"brief": brief.strip()})
        if post:
            with st.spinner("Writing the caption…"):
                api("POST", f"/linkedin/{post['id']}/caption")
            st.session_state["post_id"] = post["id"]
            goto("linkedin")


def render_linkedin(post_id: str) -> None:
    if st.button("← Back to all posts"):
        goto("home")

    po = api("GET", f"/linkedin/{post_id}")
    if not po:
        return

    st.markdown(f"## 💼 {po['brief'][:80]}")
    if po.get("error"):
        st.error(f"Last run failed — {po['error']}")

    tabs = st.tabs([
        f"{'✅' if po['has_caption'] else '📝'} 1. Caption",
        f"{'✅' if po['has_image'] else '🖼️'} 2. Image",
        "📋 3. Post it",
    ])

    # ---- 1. Caption ----
    with tabs[0]:
        st.caption("Your LinkedIn caption. Edit it freely, or regenerate a new one.")
        verb = "Regenerate caption" if po["has_caption"] else "Generate caption"
        if st.button(f"✍️ {verb}", type="primary", key="lcap_gen"):
            with st.spinner("Writing…"):
                api("POST", f"/linkedin/{post_id}/caption")
            st.rerun()
        if po["caption"]:
            edited = st.text_area("Caption", po["caption"], height=340, key="lcap_edit")
            if st.button("💾 Save caption edits"):
                if api("PUT", f"/linkedin/{post_id}/caption", {"caption": edited}):
                    st.success("Saved.")
                    st.rerun()

    # ---- 2. Image ----
    with tabs[1]:
        if not po["has_caption"]:
            st.info("🔒 Write the caption first (step 1).")
        else:
            st.caption("Describe the visual you want. The AI uses your caption + this "
                       "direction to make a square graphic.")
            img_brief = st.text_input(
                "Visual direction (optional)",
                value=po.get("image_brief") or "",
                placeholder="e.g. a glowing neural network connecting apps, dark blue, minimal",
                key="limg_brief",
            )
            verb = "Regenerate image" if po["has_image"] else "Generate image"
            if st.button(f"🖼️ {verb}", type="primary", key="limg_gen"):
                with st.spinner("Painting… (~1 min)"):
                    api("POST", f"/linkedin/{post_id}/image", {"brief": img_brief.strip()})
                st.rerun()

            if po["has_image"]:
                img = api("GET", f"/linkedin/{post_id}/image/file", raw=True)
                if img:
                    st.image(img, caption="LinkedIn post image (1:1)")
                fb = st.text_input("Change it? Describe what to adjust:",
                                   placeholder="e.g. brighter, add a robot, more orange",
                                   key="limg_fb")
                if st.button("🔄 Regenerate with feedback", disabled=not fb.strip()):
                    with st.spinner("Repainting…"):
                        api("POST", f"/linkedin/{post_id}/image/regenerate",
                            {"feedback": fb.strip()})
                    st.rerun()

    # ---- 3. Post it (manual) ----
    with tabs[2]:
        if not (po["has_caption"] and po["has_image"]):
            st.info("Finish the caption and image first.")
        else:
            st.caption("LinkedIn has no easy posting API, so post manually — it takes 20s:")
            st.markdown("1. **Copy the caption** below  \n"
                        "2. **Download the image**  \n"
                        "3. Open LinkedIn → *Start a post* → paste caption → add the image "
                        "→ **Post**")
            st.text_area("Caption (copy this)", po["caption"], height=300, key="lfinal_cap")
            img = api("GET", f"/linkedin/{post_id}/image/file", raw=True)
            if img:
                st.download_button("⬇️ Download image", img,
                                   file_name=f"linkedin-{post_id}.png", mime="image/png")


# ---------------- episode wizard ----------------

def step_state(ep: dict) -> list[dict]:
    """The 7 steps with done/unlocked flags — the single source of gating truth."""
    return [
        dict(name="Plan",    icon="🧠", done=ep["has_blueprint"], unlocked=True),
        dict(name="Script",  icon="📝", done=ep["has_script"],   unlocked=ep["has_blueprint"]),
        dict(name="Audio",   icon="🎧", done=ep["has_audio"],    unlocked=ep["has_script"]),
        dict(name="Image",   icon="🖼️", done=ep["has_image"],    unlocked=ep["has_audio"]),
        dict(name="Video",   icon="🎬", done=ep["has_video"],
             unlocked=ep["has_audio"] and ep["has_image"]),
        dict(name="Package", icon="🏷️", done=ep["has_metadata"], unlocked=ep["has_video"]),
        dict(name="Upload",  icon="🚀", done=bool(ep["youtube_video_id"]),
             unlocked=ep["has_video"] and ep["has_metadata"]),
    ]


def render_header(ep: dict, steps: list[dict]) -> None:
    st.markdown(f"## {ep['topic']}")
    label, klass = STATUS_META.get(ep["status"], (ep["status"], "pill-idle"))
    st.markdown(
        f"<span class='pill {klass}'>{label}</span> "
        f"<span class='chip'>⏱ ~{ep['target_minutes']:g} min</span>"
        f"<span class='chip'>🎤 {' & '.join(ep['hosts'])}</span>",
        unsafe_allow_html=True,
    )

    html = "<div class='steps'>"
    next_marked = False
    for i, s in enumerate(steps, 1):
        if s["done"]:
            klass = "step-done"
        elif s["unlocked"] and not next_marked:
            klass, next_marked = "step-next", True
        else:
            klass = "step-lock"
        html += f"<div class='step {klass}'>{i}. {s['icon']} {s['name']}</div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)

    if ep.get("user_context"):
        with st.expander("📚 Your knowledge for this episode (the AI grounds the content in this)"):
            st.markdown(ep["user_context"])

    if ep["status"] == "failed" and ep.get("error"):
        st.error(f"Last run failed — **{ep['error']}**\n\n"
                 "Open the step below and press its Generate button to retry.")


def locked_notice(step_num: int, requirement: str) -> None:
    st.info(f"🔒 Locked — finish **step {step_num} ({requirement})** first.")


def render_episode(ep_id: str) -> None:
    if st.button("← Back to all videos"):
        goto("home")

    ep = api("GET", f"/episodes/{ep_id}")
    if not ep:
        return
    steps = step_state(ep)
    render_header(ep, steps)

    labels = [f"{'✅' if s['done'] else s['icon']} {s['name']}" for s in steps]
    tabs = st.tabs(labels)

    # ---- 1. Plan ----
    with tabs[0]:
        st.caption("The strategist plans the episode: titles, hook, outline with open "
                   "loops. Review the plan before generating the full script.")
        verb = "Regenerate plan" if steps[0]["done"] else "Generate plan"
        if st.button(f"🧠 {verb}", type="primary", key="bp_gen"):
            with st.spinner("Planning the episode… (~30s)"):
                api("POST", f"/episodes/{ep_id}/blueprint")
            st.rerun()

        bp = (api("GET", f"/episodes/{ep_id}/blueprint") or {}).get("blueprint")
        if bp:
            st.markdown("##### 🏷️ Title options")
            for t in bp["titles"]:
                st.markdown(f"- {t}")
            st.markdown(f"##### 🪝 Hook\n> {bp['hooks'][bp['chosen_hook_index']]}")
            st.markdown(f"**Big loop:** {bp['big_loop']}")
            with st.expander("📋 Full outline"):
                for i, sec in enumerate(bp["outline"], 1):
                    st.markdown(f"**{i}. {sec['heading']}**")
                    for b in sec["beats"]:
                        st.markdown(f"- {b}")
                    st.markdown(f"- 🎭 *interrupt:* {sec['pattern_interrupt']}")
                    st.markdown(f"- 🔗 *open loop:* {sec['open_loop']}")
            st.markdown(f"**Takeaway:** {bp['takeaway']}  \n**CTA:** {bp['cta']}")

    # ---- 2. Script ----
    with tabs[1]:
        if not steps[1]["unlocked"]:
            locked_notice(1, "Plan")
        else:
            st.caption("The scriptwriter turns the plan into a natural two-host conversation.")
            verb = "Regenerate script" if steps[1]["done"] else "Generate script"
            if st.button(f"📝 {verb}", type="primary", key="sc_gen"):
                with st.spinner("Writing the episode… (1–3 min)"):
                    api("POST", f"/episodes/{ep_id}/script")
                st.rerun()

            sc = api("GET", f"/episodes/{ep_id}/script")
            if sc and sc["turns"]:
                st.markdown(f"**{sc['word_count']} words** · ~{sc['est_minutes']} min "
                            f"· ${sc['cost_usd']:.3f}")
                if st.toggle("✏️ Edit mode", key="sc_edit"):
                    raw = "\n".join(f"{t['speaker']}: {t['text']}" for t in sc["turns"])
                    new_raw = st.text_area("One line per turn — `Speaker: text`",
                                           raw, height=420)
                    if st.button("💾 Save corrections", type="primary"):
                        turns = []
                        for line in new_raw.splitlines():
                            if ":" in line:
                                spk, txt = line.split(":", 1)
                                if spk.strip() and txt.strip():
                                    turns.append({"speaker": spk.strip(),
                                                  "text": txt.strip()})
                        if turns and api("PUT", f"/episodes/{ep_id}/script",
                                         {"turns": turns}):
                            st.success("Saved.")
                            st.rerun()
                else:
                    h1 = ep["hosts"][0]
                    with st.container(height=440):
                        for t in sc["turns"]:
                            color = "blue" if t["speaker"] == h1 else "orange"
                            st.markdown(f":{color}[**{t['speaker']}**] — {t['text']}")

    # ---- 3. Audio ----
    with tabs[2]:
        if not steps[2]["unlocked"]:
            locked_notice(2, "Script")
        else:
            st.caption("The script becomes human-sounding two-voice audio. "
                       "This is the quality gate — listen before continuing.")
            verb = "Regenerate audio" if steps[2]["done"] else "Generate audio"
            if st.button(f"🎧 {verb}", type="primary", key="au_gen"):
                with st.spinner("Synthesizing voices… (1–3 min)"):
                    api("POST", f"/episodes/{ep_id}/audio")
                st.rerun()

            au = api("GET", f"/episodes/{ep_id}/audio")
            if au and au.get("audio_path"):
                st.markdown(f"**{au['duration_seconds']:.0f}s** (~{au['est_minutes']} min) "
                            f"· ${au['cost_usd']:.3f}")
                audio_bytes = api("GET", f"/episodes/{ep_id}/audio/file", raw=True)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mpeg")

    # ---- 4. Image ----
    with tabs[3]:
        if not steps[3]["unlocked"]:
            locked_notice(3, "Audio")
        else:
            im = api("GET", f"/episodes/{ep_id}/image")
            has_result = bool(im and im.get("image_path"))

            if has_result:
                st.markdown("##### ✅ Chosen design for this episode")
                col_a, col_b = st.columns(2)
                thumb = api("GET", f"/episodes/{ep_id}/thumbnail/file", raw=True)
                bg = api("GET", f"/episodes/{ep_id}/image/file", raw=True)
                if thumb:
                    col_a.image(thumb, caption="Thumbnail / intro card (topic on top)")
                if bg:
                    col_b.image(bg, caption="Video background (brand top-left)")
                st.divider()

            assets = api("GET", "/assets") or {}
            presets = assets.get("thumbnails", [])
            st.markdown("##### 🎨 Your designs (assets folder — free, instant)")
            if presets:
                st.caption("Pick a thumbnail design — the topic gets written on top "
                           "automatically. The background below is used in every video.")
                cols = st.columns(len(presets))
                for col, name in zip(cols, presets):
                    img_bytes = cached_file(f"/assets/thumbnail/{name}/file", name)
                    if img_bytes:
                        col.image(img_bytes, caption=name)
                    if col.button("✅ Use this design", key=f"preset_{name}",
                                  use_container_width=True):
                        with st.spinner("Applying design + writing the topic on it…"):
                            api("POST", f"/episodes/{ep_id}/image/preset", {"name": name})
                        st.rerun()
            else:
                st.info("No preset designs found — add `thumbnail_1.png`, "
                        "`thumbnail_2.png`… to the assets/ folder.")

            if assets.get("background"):
                with st.expander("👀 Preview the fixed video background"):
                    bg_prev = cached_file("/assets/background/file", "bg")
                    if bg_prev:
                        st.image(bg_prev, caption="assets/background.png — used in "
                                                   "every video (brand added top-left)")

            st.divider()
            st.markdown("##### 🤖 Or let AI paint a new design (~$0.06)")
            if st.button("🖼️ Generate with AI", key="im_gen"):
                with st.spinner("Painting… (~1 min)"):
                    api("POST", f"/episodes/{ep_id}/image")
                st.rerun()
            if has_result:
                fb = st.text_input("Or describe a change to the AI design:",
                                   placeholder="e.g. brighter, add plants, red shirt",
                                   key="im_fb")
                if st.button("🔄 Regenerate with my feedback", disabled=not fb.strip()):
                    with st.spinner("Repainting…"):
                        api("POST", f"/episodes/{ep_id}/image/regenerate",
                            {"feedback": fb.strip()})
                    st.rerun()

    # ---- 5. Video ----
    with tabs[4]:
        if not steps[4]["unlocked"]:
            locked_notice(4, "Audio + Image")
        else:
            st.caption("Assembles: silent intro card (2s) → talking scene where audio, "
                       "captions and waveform all start together.")
            verb = "Re-assemble video" if steps[4]["done"] else "Assemble video"
            if st.button(f"🎬 {verb}", type="primary", key="vi_gen"):
                with st.spinner("Rendering with ffmpeg… (a few minutes for long episodes)"):
                    api("POST", f"/episodes/{ep_id}/video")
                st.rerun()

            vi = api("GET", f"/episodes/{ep_id}/video")
            if vi and vi.get("video_path"):
                video_bytes = api("GET", f"/episodes/{ep_id}/video/file", raw=True)
                if video_bytes:
                    st.video(video_bytes)

    # ---- 6. Package ----
    with tabs[5]:
        if not steps[5]["unlocked"]:
            locked_notice(5, "Video")
        else:
            st.caption("The packaging: final title, SEO description with chapter "
                       "timestamps, tags.")
            verb = "Regenerate packaging" if steps[5]["done"] else "Generate packaging"
            if st.button(f"🏷️ {verb}", type="primary", key="md_gen"):
                with st.spinner("Packaging… (~30s)"):
                    api("POST", f"/episodes/{ep_id}/metadata")
                st.rerun()

            md = api("GET", f"/episodes/{ep_id}/metadata")
            if md and md.get("title"):
                new_title = st.text_input("Title", md["title"])
                new_desc = st.text_area("Description", md["description"], height=240)
                new_tags = st.text_input("Tags (comma-separated)", ", ".join(md["tags"]))
                if st.button("💾 Save packaging edits"):
                    if api("PUT", f"/episodes/{ep_id}/metadata", {
                        "title": new_title,
                        "description": new_desc,
                        "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                    }):
                        st.success("Saved.")
                        st.rerun()

    # ---- 7. Upload ----
    with tabs[6]:
        if not steps[6]["unlocked"]:
            locked_notice(6, "Video + Package")
        else:
            up = api("GET", f"/episodes/{ep_id}/upload")
            if up and up.get("youtube_video_id"):
                st.success(f"Uploaded! 🎉  Watch: {up['url']}")
                st.caption(f"Privacy: {up['privacy']} — make it public from YouTube Studio "
                           "when you're happy with it.")
                with st.expander("⚠️ Was the video removed or not showing? Upload again"):
                    st.markdown(
                        "If YouTube removed it (e.g. it was over 15 min before your "
                        "channel's *Intermediate features* were active), you can upload "
                        "a **fresh copy** now. This creates a NEW YouTube video — delete "
                        "the old dead one from YouTube Studio afterwards."
                    )
                    if st.button("🔁 Upload a fresh copy to YouTube"):
                        with st.spinner("Re-uploading…"):
                            res = api("POST", f"/episodes/{ep_id}/upload")
                        if res:
                            st.balloons()
                            st.rerun()
            else:
                st.caption("Publishes to YouTube as UNLISTED (only people with the link "
                           "can watch).")
                st.markdown("**Before you press it:** did you watch the video and read "
                            "the packaging? ✔")
                if st.button("🚀 Upload to YouTube", type="primary"):
                    with st.spinner("Uploading…"):
                        res = api("POST", f"/episodes/{ep_id}/upload")
                    if res:
                        st.balloons()
                        st.rerun()


# ---------------- router ----------------

health = backend_alive()
render_topbar(health)

view = st.session_state.get("view", "home")
if view == "episode" and st.session_state.get("episode_id"):
    render_episode(st.session_state["episode_id"])
elif view == "linkedin" and st.session_state.get("post_id"):
    render_linkedin(st.session_state["post_id"])
elif view == "create":
    render_create()
elif view == "create_linkedin":
    render_create_linkedin()
else:
    render_home()
