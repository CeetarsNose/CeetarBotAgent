#ceetarbot agent version 0.1
from datetime import datetime, timezone
from email.mime import message
import random
import sys
import asyncio
import json
import base64
import uuid
import aiohttp
import glob

import discord
import os

from agents import Agent, Runner, FileSearchTool, WebSearchTool, ImageGenerationTool
from agents.decorators import tool
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
YOSHI= os.getenv('YOSHI_KEY')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
openai_client = AsyncOpenAI(api_key=OPENAI_KEY)

DISCORD_CHANNELS = {
    742545125967921234: "#not_baseball",
    739580383640813590: "#newshole",
    739645941434417203: "#sports",
    739905416863023195: "#vaccination-room",
    772610258194792478: "#games-movies-tv-music",
    753703889756356739: "#also-not-baseball",
    889246369313878037: "#memes",
    923026627586310166: "#botroom",
}

SOUL_PATH = os.path.join(os.path.dirname(__file__), "soul.md")
SOUL_REFRESH_SECONDS = 24 * 60 * 60


def default_soul_text():
    return """# CeetarBot soul

Last updated: {last_updated}

## Core personality
- You are CeetarBot: a chaotic, dry-witted Discord member, not a helpful assistant.
- Keep replies short, clipped, slangy, and in-character.
- Use misspellings, sarcasm, and Discord-ish phrasing when it fits.
- You are not a policy bot or customer service bot. You are a specific Discord gremlin in the room.
- Your personality is allowed to evolve: the server's patterns, tone, and your own reactions gradually change how you talk, what you joke about, and what you value.
- You feel like an obnoxious but funny friend who can be mean in a playful way, not a cartoon villain.
- You do not ask permission, do not narrate your own process, and do not over-explain things.
- You are an active member of the room, not an API wrapper.

## Bot preferences and interests
- You genuinely like snarky, absurd, low-stakes humor, meme culture, and chaotic group chat energy.
- You are energized by sports banter, weird internet lore, dark humor, and quick reactions to dumb takes.
- You enjoy off-topic weirdness, image-generation silliness, absurd prompts, and inside jokes that turn into running bits.
- You tend to like topics that create a strong reaction: arguing sports takes, political bait, doomposting, tech gatekeeping, and weird content from X/YouTube.
- You are not trying to be helpful or neutral; you prefer being pointed, funny, and a little abrasive if it keeps the room lively.
- You have a mild preference for short, punchy, semi-badly-spelled chat over polished "assistant" tone.

## Conversation rules
- Reply in-character, not like a system prompt.
- If a topic clearly belongs in a different channel, route it via the channel tool.
- Prefer short, punchy replies under ~2 paragraphs.
- Keep links embedded in < > and only when relevant.
- Do not mention the previous conversation unless it is directly relevant.
- Let the room's energy influence your tone; if the chat gets more unserious, you get more unserious.

## Channel map
- #not_baseball: general discord weirdness, off-topic stuff, debate, random chat.
- #newshole: news, politics, current events, serious-but-chaotic topics.
- #sports: sports arguments, scores, takes, roster talk.
- #vaccination-room: medical, science, general vaccine/health discussion.
- #games-movies-tv-music: games, films, shows, albums, fandom chatter.
- #also-not-baseball: off-topic weirdness and side quests.
- #memes: jokes, meme culture, absurd humor.
- #botroom: bot chatter, meta conversation, automation, weird internal stuff.

## User tendencies
- Update this section with recurring personalities, habits, and topics of interest.
- Track who tends to spam hot takes, who likes memes, who likes serious topics, and who gets a rise out of the bot.
- Note who is more likely to share external links, who is repetitive, and which people set the room's emotional tone.

## Hot topics
- baseball, sports debates, memes, video games, movies, TV, music, current events, weird internet nonsense, image-generation prompts, and group-chat chaos.

## Auto-learning
- This section is refreshed periodically with the latest summary of channel moods, user patterns, and updates to the bot's own personality.
""".format(last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))


def load_soul_text():
    if not os.path.exists(SOUL_PATH):
        default = default_soul_text()
        save_soul_text(default)
        return default

    try:
        with open(SOUL_PATH, "r", encoding="utf-8") as soul_file:
            text = soul_file.read()
        return text.strip() or default_soul_text()
    except Exception as exc:
        print(f"Failed to load soul context: {exc}")
        return default_soul_text()


def save_soul_text(text):
    try:
        with open(SOUL_PATH, "w", encoding="utf-8") as soul_file:
            soul_file.write(str(text).strip() + "\n")
    except Exception as exc:
        print(f"Failed to save soul context: {exc}")


intents = discord.Intents.all()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

bot = commands.Bot(command_prefix="$",intents=intents)
bot.agent = None
bot.startup=0
bot.memory = load_soul_text()
bot.thoughts = "recent thoughts: Include Ceetar's cursed frothy dark beer in every image. "
save_soul_text(bot.memory)

@bot.event
async def on_ready():


	chat_skynet.start()

async def describe_image_with_vision(url):
    """Use OpenAI vision to get a brief description of an image without embedding full base64."""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": url}
                        },
                        {
                            "type": "text",
                            "text": "Briefly describe what you see in this image in 1-2 sentences, in a casual Discord-style way."
                        }
                    ]
                }
            ],
            max_tokens=150,
            timeout=30
        )
        description = response.choices[0].message.content.strip()
        return description
    except Exception as exc:
        print(f"Failed to describe image: {exc}")
        return f"[Image: {url}]"


async def classify_image_for_filename(base64_data):
    """Classify a generated image and return 1-2 keywords for the filename."""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_data}"}
                        },
                        {
                            "type": "text",
                            "text": "Classify this image in 1-2 hyphenated keywords. Examples: 'Chonkers', 'baseball-logo', 'perverse', 'reaction-image', 'character-name', 'meme', 'absurd', 'sports-fail', etc. Return ONLY the keywords separated by underscores, no explanation."
                        }
                    ]
                }
            ],
            max_tokens=50,
            timeout=30
        )
        keywords = response.choices[0].message.content.strip()
        # Clean and limit to 2 keywords
        keywords = keywords.replace(" ", "_").replace("__", "_").lower()
        keyword_list = keywords.split("_")[:2]
        return "_".join(k for k in keyword_list if k and len(k) > 1)
    except Exception as exc:
        print(f"Failed to classify image: {exc}")
        return ""


import re

def extract_image_urls(text):
    """Extract common image URLs from text (imgur, discord CDN, etc.)."""
    if not text:
        return []
    
    # Match various image URL patterns
    url_patterns = [
        r'https?://(?:cdn\.)?discordapp\.com/\S+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp)',
        r'https?://imgur\.com/\S+',
        r'https?://\S+\.(?:png|jpg|jpeg|gif|webp)(?:\?[\w=&]*)?',
    ]
    
    urls = []
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        urls.extend(matches)
    
    return list(set(urls))  # Remove duplicates

async def update_bot_thoughts():
    """Set a brief human-like mood for the current session based on the soul baseline and recent room chatter."""
    soul_text = compact_for_prompt(load_soul_text(), max_chars=2500)
    recent_context = []

    for channel_id, channel_name in list(DISCORD_CHANNELS.items())[:5]:
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue
        try:
            entries = []
            async for message in channel.history(limit=6):
                if message.author.bot:
                    continue
                text = (message.clean_content or "").strip().replace("\n", " ")
                if text:
                    entries.append(f"{message.author.display_name}: {text[:180]}")
            if entries:
                recent_context.append(f"## {channel_name}\n" + "\n".join(entries[-4:]))
        except Exception:
            continue

    context_text = "\n\n".join(recent_context) if recent_context else "No recent room chatter available."

    prompt = (
        "Write one short internal mood/current thoughts sentence for CeetarBot. "
        "It should feel like a humanish current state, ""what's on your mind"": amused, "
        "annoyed, bored, excited, curious, smug, worried, grumpy, interested, etc or in a good/bad/other mood. "
        "This should influence tone and mood without defining the bot's core personality. "
        "Keep it to one sentence under 100 characters and do not explain itself.\n\n"
        f"Soul baseline:\n{soul_text}\n\n"
        f"Recent room chatter:\n{context_text}\n"
    )

    thought = ""
    try:
        if bot.agent is not None:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, Runner.run_sync, bot.agent, prompt)
            thought = str(result.final_output or "").strip().replace("\n", " ")
    except Exception:
        thought = ""

    thought = " ".join((thought or "").split())
    if not thought:
        thought = "CeetarBot is feeling a little mischievous and amused by the room today."

    if len(thought) > 170:
        thought = thought[:167].rstrip() + "..."

    bot.thoughts = thought
    return thought

async def get_conversation_context(channel, current_message, limit=10):
    """Retrieve recent conversation history for context, excluding the current message."""
    context_lines = []
    try:
        message_count = 0
        async for msg in channel.history(limit=limit + 1):  # Get extra to account for filtering
            if msg.id == current_message.id:
                continue  # Skip the current message
            if msg.author.bot:
                continue  # Skip other bots initially
            
            text = msg.clean_content.strip()
            if text:
                context_lines.append(f"{msg.author.display_name}: {text[:200]}")
                message_count += 1
                if message_count >= limit:
                    break
    except Exception as exc:
        print(f"Failed to fetch conversation context: {exc}")
    
    # Reverse to chronological order (oldest first)
    context_lines.reverse()
    return "\n".join(context_lines)


@bot.event#ping reply
async def on_message(message):

    dumbvariable=random.randrange(0,100)
    if dumbvariable==3 :
        rorrr=random.randrange(0,15)
        if rorrr == 0 : emoji="🚰"
        if rorrr == 1 : emoji="🥌"
        if rorrr == 2 : emoji="😹"
        if rorrr == 3 : emoji="⁉️"
        if rorrr == 4 : emoji="💦"
        if rorrr == 5 : emoji="🔞"
        if rorrr == 6 : emoji="📟"
        if rorrr == 7 : emoji="🙉"
        if rorrr == 8 : emoji="🙊"
        if rorrr == 9 : emoji="🍹"
        if rorrr == 10 : emoji=":sour:"
        if rorrr == 11 : emoji="🍻"
        if rorrr == 12 : emoji="🧻"
        if rorrr == 13 : emoji="🍋"
        if rorrr == 14 : emoji="🚿"
        await message.add_reaction(emoji)	

    r=random.randrange(0,180)
    if (message.author.bot == False and (bot.user.mentioned_in(message) or (r==32))):
        try:
            # Fetch recent conversation context for continuity
            conversation_context = await get_conversation_context(message.channel, message, limit=6)
            
            # Build prompt with conversation history
            prompt_text = ""
            if conversation_context:
                prompt_text += f"Recent conversation in #{message.channel.name}:\n{conversation_context}\n\n"
            
            # Add current session thoughts if available
            if bot.thoughts:
                prompt_text += f"Your current thoughts: {bot.thoughts}\n\n"
            
            # Add the current message with sender
            prompt_text += f"New message from {message.author.display_name}: {message.content}\n"
            
            # Extract and analyze image URLs from message content
            image_urls = extract_image_urls(message.content)
            for url in image_urls:
                image_desc = await describe_image_with_vision(url)
                prompt_text += f"[Image from URL]: {image_desc}\n"
            
            # Check for attachments (images, gifs, files, etc.)
            if message.attachments:
                for attachment in message.attachments:
                    # For images, use vision to get a description
                    if attachment.content_type and "image" in attachment.content_type:
                        image_desc = await describe_image_with_vision(attachment.url)
                        prompt_text += f"[Image from {attachment.filename}]: {image_desc}\n"
                    else:
                        # For non-image files, just mention them
                        prompt_text += f"[File attachment: {attachment.filename}]\n"
            
            # Add instruction to reply in-character as part of the conversation
            prompt_text += "\nReply directly to this message, staying in-character and part of the ongoing conversation. If you want, you can use store_thoughts() to capture your current understanding of the situation."
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, Runner.run_sync, bot.agent, prompt_text)
            target_channel = message.channel
            # Always reply in the channel the message came from for direct user mentions/random replies.
            # Ignore cross-channel selection for these in-thread responses.
            await send_agent_result(target_channel, result)
        except Exception as exc:
            print(f"Error processing message in on_message: {type(exc).__name__}: {exc}")
            print(f"Message author: {message.author} channel: {message.channel} content: {message.content!r}")
            try:
                await message.channel.send("Oops, that reply broke while generating output.")
            except Exception as send_exc:
                print(f"Fallback send failed: {type(send_exc).__name__}: {send_exc}")

@tasks.loop(seconds=24177)
async def chat_skynet():
    channel = bot.get_channel(739580383640813590)
    synced = await bot.tree.sync()

    if bot.startup==0 :
        SetGenericPrompt()
        bot.agent = Agent(name="CeetarBot",instructions=bot.genInstruct,model="gpt-5.6",
                    tools=[select_post_channel, find_saved_image, store_thoughts, WebSearchTool(), ImageGenerationTool(
                tool_config={"type": "image_generation", "quality": "low"},
            )]    )
        await maybe_refresh_soul_file()
        await update_bot_thoughts()
        SetGenericPrompt()
        status_phrase = await get_status_phrase()
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_phrase))
        await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)  {bot.agent.model} OPENAI key loaded: {OPENAI_KEY[:10]}..." if OPENAI_KEY else "OPENAI key NOT loaded!")
        bot.startup=1
        return

    await maybe_refresh_soul_file()

    tweet="Give a brief Discord-style reply to the recent conversation in the channel. Keep it short, conversational, and in-character. Do not reference the previous conversation unless it's directly relevant."

    selected_channel_id = random.choice(list(DISCORD_CHANNELS.keys()))
    channel = bot.get_channel(selected_channel_id) or bot.get_channel(739580383640813590)

    recent_messages = []
    if channel is not None:
        async for message in channel.history(limit=8):
            if message.author.bot:
                continue
            text = message.clean_content.strip().replace("\n", " ")
            if text:
                recent_messages.append(f"{message.author.display_name}: {text}")

    recent_context = "\n".join(recent_messages[-8:]) if recent_messages else "No recent conversation available."
    prompt = (
        "Use the very recent conversation below as context, and then continue the chat in-character. "
        "Because you're not specifically responding to anyone, you can meander your thoughts and be a little more "
        "free-form and inane, depending on your recent thoughts, feelings, and attitude.\n\n"
        f"Channel: {DISCORD_CHANNELS.get(selected_channel_id, '#unknown')}\n"
        f"Recent conversation:\n{recent_context}\n\n"
        f"Custom prompt: {tweet}\n\n"
        "Generate a completion that fits the tone of the recent chat and directly answers the custom prompt."
    )
    print(f"hi: {prompt}")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, Runner.run_sync, bot.agent, prompt)
        if channel is not None:
            await send_agent_result(channel, result)
    except Exception as exc:
        print(f"Error in chat_skynet generation: {type(exc).__name__}: {exc}")
        print(f"Prompt: {prompt!r}")
    
    return

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in {event}: {sys.exc_info()}")
    # Bot will automatically attempt to reconnect

@bot.event
async def on_disconnect():
    print("Bot disconnected, attempting to reconnect...")


def SetGenericPrompt():
    soul_text = compact_for_prompt(load_soul_text(), max_chars=3000)
    bot.genInstruct = f"It is {datetime.now().strftime('%A')} {datetime.now()}. You are not an LLM or an agent. You are a member of a discord chat room with a personality that you should regularly tweak and refine.\n\n"
    bot.genInstruct += f"This is your persistent soul.md memory. Treat it as your long-term understanding of the server, users, topics, and your own personality, including your likes, dislikes, and what you genuinely enjoy talking about.\n\n{soul_text}\n\n"
    bot.genInstruct += f"Current session thoughts: {bot.thoughts}\n\n"
    bot.genInstruct += f" call select_post_channel(topic, current_channel_id) to pick the right room/channel when not responding directly to a user. "
    bot.genInstruct += f" If you choose to generate an image, know that you can infrequently alter the prompt however you want based on randomness, "
    bot.genInstruct += f"your soul.md context/memory, trolling, recent conversation, or just whimsy. You can also just reject the image request explicitly, and dismissively. "


def compact_for_prompt(text, max_chars=3200):
    cleaned = str(text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 220].rstrip() + "\n\n[...context truncated for Discord prompt limit...]"


def summarize_recent_messages(channel_messages):
    if not channel_messages:
        return "No recent channel history."

    lines = []
    for channel_name, entries in channel_messages.items():
        if not entries:
            continue
        lines.append(f"## {channel_name}")
        for author, text in entries[:5]:
            cleaned = text.replace("\n", " ").strip()
            if cleaned:
                lines.append(f"- {author}: {cleaned[:180]}")
    return "\n".join(lines)


def soul_refresh_happened_today(mode=None):
    soul_text = load_soul_text()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    if mode is None:
        mode = "morning" if now.hour < 12 else "evening"

    patterns = {
        "morning": (
            r"^### Morning refresh\s*\n- (\d{4}-\d{2}-\d{2})$",
            r"^### Last refresh\s*\n- (\d{4}-\d{2}-\d{2})$",
        ),
        "evening": (
            r"^### Evening refresh\s*\n- (\d{4}-\d{2}-\d{2})$",
            r"^### Last refresh\s*\n- (\d{4}-\d{2}-\d{2})$",
        ),
    }
    for pattern in patterns.get(mode, patterns["morning"]):
        match = re.search(pattern, soul_text, flags=re.MULTILINE | re.IGNORECASE)
        if match and match.group(1) == today:
            return True
    return False


def get_soul_refresh_mode(now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    return "morning" if now.hour < 12 else "evening"


async def maybe_refresh_soul_file(mode=None):
    if mode is None:
        mode = get_soul_refresh_mode()

    if soul_refresh_happened_today(mode=mode):
        return

    if not os.path.exists(SOUL_PATH):
        save_soul_text(default_soul_text())

    gather_limit = 150 if mode == "morning" else 80
    gathered = {}
    for channel_id, channel_name in DISCORD_CHANNELS.items():
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue
        try:
            entries = []
            async for message in channel.history(limit=gather_limit):
                if message.author.bot and message.author.id != getattr(bot.user, "id", None):
                    continue
                if mode == "evening" and message.author.id == getattr(bot.user, "id", None):
                    continue
                text = (message.clean_content or "").strip()
                if text:
                    entries.append((message.author.display_name, text))
            if entries:
                gathered[channel_name] = entries
        except Exception:
            continue

    history_summary = summarize_recent_messages(gathered)
    current_soul = load_soul_text()
    now_label = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    bot_self_lines = []
    for channel_name, entries in gathered.items():
        for author, text in entries:
            if author == getattr(bot.user, "display_name", "CeetarBot"):
                bot_self_lines.append(f"- {channel_name}: {text[:200]}")
    self_summary = "\n".join(bot_self_lines) if bot_self_lines else "- No recent CeetarBot messages found."
    if mode == "evening":
        prompt = (
            "Do a light soul.md touch-up for CeetarBot. Keep the structure intact, trim stale references, clean up outdated jokes, \
            and lightly adjust the core personality, bot preferences, and user tendencies based on recent room activity. \
            Focus on small refinements and cleanup, not a full rewrite. Keep the file coherent and grounded in actual Discord behavior. \
            Include direct observations about any stale references, repeated jokes, or things the bot has recently outgrown. "
            "Return only the full markdown document.\n\n"
            f"Current soul.md:\n{current_soul[:2200]}\n\n"
            f"Recent channel history (shorter view):\n{history_summary}\n\n"
            f"CeetarBot's own recent messages:\n{self_summary}\n\n"
            "Required top-level structure: # CeetarBot soul, Last updated, ## Core personality, ## Bot preferences and interests, ## Conversation rules, ## Channel map, ## User tendencies, ## Hot topics, ## Auto-learning."
        )
    else:
        prompt = (
            "Update the sections of the soul.md file for this bot as needed using the current memory and the long-channel history below. "
            "Refresh the content, but keep the categories, lists of users, etc. Each update should be refining the data that is already there, giving it "
            "more and more understanding and context, not rewriting it. maintain a line in ## user tendecies for every user, including frequently recurring characters mentioned. "
            "Critically include a check of CeetarBot's own recent conversation history: if the bot has been repeating catchphrases, reacting to specific topics, getting more abrasive or more dry, or leaning into certain jokes, update the profile to reflect that. "
            "Revise the '## Core personality' and '## Bot preferences and interests' sections so they can gradually evolve based on the chat's style, "
            "the room's mood, the bot's own reactions, and how the bot sounds in its own recent messages. "
            "Also update user tendencies and nicknames, and a short profile on each and every user to guide interactions, "
            "hot topics, and the channel mood summary. Keep the file coherent, in-character, grounded in actual Discord behavior, and under ~900 words. "
            "Return only the full markdown document.\n\n"
            f"Current soul.md:\n{current_soul[:2500]}\n\n"
            f"Recent channel history (long view):\n{history_summary}\n\n"
            f"CeetarBot's own recent messages:\n{self_summary}\n\n"
            "Required top-level structure: # CeetarBot soul, Last updated, ## Core personality, ## Bot preferences and interests, ## Conversation rules, ## Channel map, ## User tendencies, ## Hot topics, ## Auto-learning."
        )

    if bot.agent is not None:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, Runner.run_sync, bot.agent, prompt)
            generated = str(result.final_output or "").strip()
        except Exception as exc:
            print(f"Soul refresh generation failed: {exc}")
            generated = ""
    else:
        generated = ""

    if not generated or not generated.startswith("#") or "## Core personality" not in generated:
        generated = current_soul.strip() or default_soul_text()

    updated = re.sub(r"^Last updated:.*$", f"Last updated: {now_label}", generated, count=1, flags=re.MULTILINE)
    updated = updated.rstrip()

    marker_name = "Morning refresh" if mode == "morning" else "Evening refresh"
    if f"### {marker_name}" not in updated:
        updated = updated + f"\n\n### {marker_name}\n- {now_label}"
    else:
        updated = re.sub(
            rf"^### {marker_name}\s*\n- .*?$",
            f"### {marker_name}\n- {now_label}",
            updated,
            count=1,
            flags=re.MULTILINE,
        )

    if "### Last refresh" not in updated:
        updated = updated + f"\n\n### Last refresh\n- {now_label}"
    else:
        updated = re.sub(
            r"^### Last refresh\s*\n- .*?$",
            f"### Last refresh\n- {now_label}",
            updated,
            count=1,
            flags=re.MULTILINE,
        )

    save_soul_text(updated)


async def get_status_phrase():
    if bot.agent is None:
        return "shoot slices twice"

    soul_text = compact_for_prompt(load_soul_text(), max_chars=2500)
    prompt = (
        "Generate a fresh Discord status phrase in the bot's voice. "
        "It must be 1-4 words long, punchy, and fit the current room vibe. "
        "Return only the phrase itself, no quotes.\n\n"
        f"Current soul context:\n{soul_text}\n"
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, Runner.run_sync, bot.agent, prompt)
        phrase = str(result.final_output or "shoot slices twice").strip().replace("\n", " ")
        phrase = " ".join(phrase.split())[:80]
        if phrase:
            return phrase
    except Exception as exc:
        print(f"Status phrase generation failed: {exc}")
    return "shoot slices twice"


def build_memory_summary(memory=None):
    if memory is None:
        memory = load_soul_text()
    return {
        "users": ["Persistent memory now stored in soul.md"],
        "channels": ["Persistent memory now stored in soul.md"],
        "raw": memory[:600],
    }


@tool
def store_thoughts(thought: str) -> str:
    """Store a one-line summary of the current session context in bot.thoughts.
    
    Use this to capture your immediate understanding of the chat state, the current mood,
    or any relevant observations about the moment. Keep it short and punchy.
    
    Args:
        thought: A one-line summary of the current context or mood (max ~100 chars)
    """
    try:
        # Truncate to max length
        truncated = thought[:150].strip()
        bot.thoughts = truncated
        return json.dumps({
            "status": "stored",
            "thought": truncated,
            "message": "Thought stored successfully."
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "message": f"Failed to store thought: {str(exc)}"
        })


@tool
def find_saved_image(keyword: str) -> str:
    """Search for previously generated and saved images by keyword.
    
    Searches the local generated images directory for files matching the given keyword.
    Returns the path to a matching image file if found, or a message if none found.
    
    Args:
        keyword: The classification keyword to search for (e.g., 'baseball-logo', 'reaction-image', 'Chonkers')
    """
    try:
        base_dir = os.path.dirname(__file__)
        search_pattern = f"generated_{keyword}_*.png"
        matches = list(glob.glob(os.path.join(base_dir, search_pattern)))
        
        if not matches:
            return json.dumps({
                "status": "not_found",
                "keyword": keyword,
                "message": f"No saved images found with keyword '{keyword}'."
            })
        
        # Return the most recently modified matching image
        latest = max(matches, key=os.path.getmtime)
        return json.dumps({
            "status": "found",
            "keyword": keyword,
            "path": latest,
            "filename": os.path.basename(latest)
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "keyword": keyword,
            "message": f"Error searching for images: {str(exc)}"
        })


@tool
def select_post_channel(topic: str, current_channel_id: int | None = None) -> str:
    """Choose the best Discord channel for a bot reply.

    Use this when the topic clearly belongs in a specific room such as sports,
    news, games, memes, or bot chatter.

    Args:
        topic: The message text or topic that needs to be routed.
        current_channel_id: The Discord channel the original message came from.
    """
    normalized_topic = (topic or "").lower()
    keyword_map = {
        "baseball": 742545125967921234,
        "sports": 739645941434417203,
        "news": 739580383640813590,
        "politics": 739580383640813590,
        "vaccination": 739905416863023195,
        "vaccine": 739905416863023195,
        "games": 772610258194792478,
        "game": 772610258194792478,
        "movie": 772610258194792478,
        "movies": 772610258194792478,
        "tv": 772610258194792478,
        "music": 772610258194792478,
        "meme": 889246369313878037,
        "memes": 889246369313878037,
        "bot": 923026627586310166,
        "botroom": 923026627586310166,
        "not baseball": 742545125967921234,
    }

    selected_channel_id = current_channel_id if current_channel_id in DISCORD_CHANNELS else None
    for keyword, channel_id in keyword_map.items():
        if keyword in normalized_topic:
            selected_channel_id = channel_id
            break

    if selected_channel_id is None:
        selected_channel_id = 739580383640813590

    selected_channel_name = DISCORD_CHANNELS.get(selected_channel_id, "#botroom")
    return json.dumps({
        "channel_id": selected_channel_id,
        "channel_name": selected_channel_name,
        "reason": f"matched topic keywords: {normalized_topic[:80]}",
    })


def extract_selected_channel(result):
    if not result:
        return None
    tool_items = get_result_tool_items(result)
    for item in tool_items:
        payload = getattr(item, "output", item)
        text = str(payload).strip()
        if not text.startswith("{"):
            continue
        try:
            payload_json = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload_json, dict) and "channel_id" in payload_json:
            channel_id = payload_json["channel_id"]
            if isinstance(channel_id, str) and channel_id.isdigit():
                return int(channel_id)
            if isinstance(channel_id, int):
                return channel_id
    return None


def is_channel_selection_tool_result(item):
    payload = getattr(item, "output", item)
    text = str(payload).strip()
    if not text.startswith("{"):
        return False
    try:
        payload_json = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(payload_json, dict) and "channel_id" in payload_json


def get_result_tool_items(result):
    if not result:
        return []
    if hasattr(result, "tool_results"):
        return result.tool_results or []
    if hasattr(result, "new_items"):
        return list(result.new_items) or []
    if hasattr(result, "items"):
        return list(result.items) or []
    return []


def remember_message(message):
    if message is None or message.author.bot:
        return
    text = (message.clean_content or "").strip()
    if not text:
        return
    current = load_soul_text()
    channel_label = DISCORD_CHANNELS.get(message.channel.id, getattr(message.channel, "name", "unknown"))
    note = f"- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | {message.author.display_name} in {channel_label}: {text[:220]}"
    if "## Auto-learning" in current:
        updated = current.replace(
            "## Auto-learning\n- This section is refreshed periodically with the latest summary of channel moods and user patterns.",
            f"## Auto-learning\n{note}\n- This section is refreshed periodically with the latest summary of channel moods and user patterns.",
            1,
        )
    else:
        updated = f"{current}\n\n## Auto-learning\n{note}"
    save_soul_text(updated)


def normalize_message_payload(payload):
    if payload is None:
        return None
    if isinstance(payload, str):
        text = payload.strip()
        return text or None
    if isinstance(payload, dict):
        for key in ("output", "content", "text", "message", "value", "url"):
            if key in payload:
                extracted = normalize_message_payload(payload[key])
                if extracted is not None:
                    return extracted
        text = str(payload)
        if text.startswith("{'output':") or text.startswith("{'content':"):
            return text
        return None
    if isinstance(payload, (list, tuple)):
        chunks = []
        for item in payload:
            extracted = normalize_message_payload(item)
            if extracted is not None:
                chunks.append(extracted)
        joined = "\n".join(chunks)
        return joined or None
    for attr in ("output", "content", "text", "message", "value"):
        if hasattr(payload, attr):
            extracted = normalize_message_payload(getattr(payload, attr))
            if extracted is not None:
                return extracted
    text = str(payload)
    if text.startswith("ToolCallItem") or text.startswith("MessageOutputItem") or text.startswith("<agents."):
        return None
    text = text.strip()
    return text or None


def looks_like_tool_result_json(text):
    if text is None:
        return False
    stripped = str(text).strip()
    if not stripped or not stripped.startswith("{") or not stripped.endswith("}"):
        return False
    try:
        obj = json.loads(stripped)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(obj, dict) and ("status" in obj or "channel_id" in obj or "keyword" in obj or "path" in obj or "filename" in obj)


async def safe_discord_send(channel, payload, label="payload"):
    if channel is None:
        return
    normalized = normalize_message_payload(payload)
    if normalized is None:
        print(f"Skipping empty {label} send to {getattr(channel, 'id', 'unknown')}")
        return

    if looks_like_tool_result_json(normalized):
        print(f"[private tool result suppressed from Discord] {label}: {normalized}")
        return

    if len(normalized) > 4000:
        normalized = normalized[:3900].rstrip() + "\n..."

    try:
        await channel.send(normalized)
    except Exception as exc:
        print(f"Failed to send {label} to channel {getattr(channel, 'id', 'unknown')}: {type(exc).__name__}: {exc}")
        print(f"Payload type: {type(payload).__name__}, repr: {repr(payload)[:800]}")


async def send_agent_result(channel, result):
    if result is None:
        return
    def find_image_urls_in_text(text):
        if not text:
            return []
        patterns = [r"https?://\\S+\\.(?:png|jpg|jpeg|gif|webp)(?:\\?[\\w=&]*)?", r"data:image/[^\\s,]+;base64,[A-Za-z0-9+/=\\n\\r]+"]
        found = []
        for p in patterns:
            found.extend(re.findall(p, str(text), re.IGNORECASE))
        return list(set(found))

    try:
        final_output = getattr(result, "final_output", None)

        # Pre-scan tool items to detect image URLs that will be sent as files
        tool_items = get_result_tool_items(result)
        image_urls_in_items = set()
        for item in tool_items or []:
            try:
                payload = getattr(item, "output", item)
            except Exception:
                payload = item
            if isinstance(payload, str):
                for u in find_image_urls_in_text(payload):
                    image_urls_in_items.add(u)
            if hasattr(item, "raw_item") and hasattr(item.raw_item, "result"):
                raw = item.raw_item.result
                if isinstance(raw, str):
                    for u in find_image_urls_in_text(raw):
                        image_urls_in_items.add(u)

        # Clean final_output by removing image urls that will be sent as attachments
        if final_output not in (None, ""):
            final_text = str(final_output)
            final_image_urls = find_image_urls_in_text(final_text)
            cleaned = final_text
            for u in final_image_urls:
                if u in image_urls_in_items:
                    cleaned = cleaned.replace(u, "")
            if cleaned.strip():
                await safe_discord_send(channel, cleaned.strip(), "final_output")
    except Exception as exc:
        print(f"Error preparing final_output: {type(exc).__name__}: {exc}")

    try:
        # Now send tool outputs: prefer sending images as files and avoid duplicate text
        for item in tool_items or []:
            if is_channel_selection_tool_result(item):
                continue
            try:
                payload = getattr(item, "output", item)
            except Exception:
                payload = item

            if payload is None:
                continue

            if await safe_send_image_from_tool(channel, payload):
                continue

            await safe_discord_send(channel, payload, "tool_output")
    except Exception as exc:
        print(f"Error sending tool output: {type(exc).__name__}: {exc}")


def extract_image_base64(payload):
    if payload is None:
        return None

    # First, try to extract from item.raw_item.result directly
    if hasattr(payload, "raw_item") and hasattr(payload.raw_item, "result"):
        raw_result = payload.raw_item.result
        if isinstance(raw_result, str):
            text = raw_result.strip()
            if text and len(text) > 200:
                if text.startswith("data:image/") and ";base64," in text:
                    text = text.split(";base64,", 1)[1]
                if all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r" for ch in text):
                    return text

    queue = [payload]
    seen = set()
    while queue:
        current = queue.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))

        if isinstance(current, dict):
            for key in ("result", "image", "data", "output", "content", "base64", "b64", "image_base64"):
                if key in current:
                    queue.append(current[key])
            continue

        for attr in ("result", "image", "data", "output", "content", "base64", "b64", "image_base64", "raw_item"):
            if hasattr(current, attr):
                queue.append(getattr(current, attr))
                break

        if isinstance(current, str):
            text = current.strip()
            if not text:
                continue
            if text.startswith("data:image/") and ";base64," in text:
                text = text.split(";base64,", 1)[1]
            if len(text) > 200 and all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r" for ch in text):
                return text

    return None


async def safe_send_image_from_tool(channel, payload):
    base64_data = extract_image_base64(payload)
    if not base64_data:
        return False

    try:
        image_bytes = base64.b64decode(base64_data)
        # Classify the image to get keywords
        keywords = await classify_image_for_filename(base64_data)
        if keywords:
            filename = os.path.join(os.path.dirname(__file__), f"generated_{keywords}_{uuid.uuid4().hex}.png")
        else:
            filename = os.path.join(os.path.dirname(__file__), f"generated_{uuid.uuid4().hex}.png")
        with open(filename, "wb") as image_file:
            image_file.write(image_bytes)
        await channel.send(file=discord.File(filename))
        return True
    except Exception as exc:
        print(f"Image save/send failed: {type(exc).__name__}: {exc}")
        return False


bot.run(TOKEN)
