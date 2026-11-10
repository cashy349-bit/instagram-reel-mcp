---
name: reel-idea-monetization-filter
description: Use whenever content fetched via the instagram-reel-mcp tool (or any viral short-form video) shows a tech idea, app concept, API integration, or "build this" tutorial. Evaluates whether the idea is a viable, monetizable problem statement — not just a replicable demo — before treating it as a project worth building.
---

# Reel Idea -> Monetizable Problem Filter

## Why this exists
A viral reel showing "connect X API to Y API" is a demo, not a business.
If a reel is getting real reach, thousands of viewers with dev skills
can clone the exact same thing within days. Clones compete on nothing —
same feature set, same audience, zero differentiation — so most of
them get zero customers. Before treating a reel's idea as worth
building, run it through this filter.

## The filter — answer in order, stop at the first hard "no"

1. **Saturation check** — Is this a novel integration, or a viral
   format (e.g. "wrap GPT around X", "turn Y into a chatbot")? Viral +
   trivially clonable + no moat = tutorial, not a product. Say so
   plainly.
2. **Underlying problem, not the surface demo** — What pain is the
   creator actually solving, underneath the flashy UI? State it in one
   sentence naming a specific person or role. Can't name one? It's a
   feature, not a problem statement yet.
3. **Who pays, and why now** — Identify the buyer (not just the user).
   What do they do today instead — manual work, a worse tool, nothing?
   What forces the switch?
4. **The narrow wedge** — Don't rebuild the whole demo. Find the
   smallest slice where you can be meaningfully better: a vertical, a
   workflow, a data source, a language/region/compliance gap the
   original's broad demo skips. Name it concretely.
5. **Distribution reality** — If 2,000-3,000 people can clone this
   from the same reel, assume they will. What does this builder have
   that the clones don't — an existing audience, domain access, a
   dataset, a relationship in the vertical — that wins *distribution*,
   not just wins the build?
6. **Monetization shape** — State the actual revenue model: per-seat
   subscription, usage metering, B2B license, transaction cut,
   services-attached. "Ads later" / "freemium, figure it out" fails
   this step.

## Output format
- One-line verdict: **Tutorial (skip)** / **Feature, not a product** /
  **Viable wedge — worth scoping**
- If viable: wedge, buyer, monetization shape — 3-4 lines, no padding
- If not viable: the exact reason in one line (saturation / no
  distribution edge / no real payer) — don't soften it

## Never do
- Never present "here's how to replicate this reel" as a business idea
  on its own.
- Never recommend a 1:1 clone of a viral demo, however impressive it
  is to build.
- Never treat the reel's view/like count as demand validation for
  *your* version — high reach validates the format's reach, not
  demand for a clone of it.

## Same filter applies to `discover_trending_by_hashtag` results
Pulling the top 5 reels in a niche has the identical saturation trap,
one level up: if 5 reels are already visibly doing the same format,
the honest read is "this format works right now" — not "recreate all
5." Use the batch to find the *pattern* (hook style, pacing, audio
choice, structural beat), then apply steps 1-6 above to whatever
specific angle you'd actually post, not to the reels themselves.
