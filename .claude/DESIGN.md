---
name: Not ChatGPT
description: A RAG PDF chatbot that shows its work — hybrid search, persistent history, and live telemetry in a clean, minimal workspace.
colors:
  iris: "#7c3aed"
  iris-deep: "#3b1fa8"
  iris-tint: "#f3f0ff"
  iris-hover: "#f0ecff"
  iris-faint: "#ede9fe"
  iris-soft: "#f5f3ff"
  iris-mid: "#c4b5fd"
  canvas: "#ffffff"
  fog: "#fafafa"
  ink: "#111111"
  slate: "#374151"
  iron: "#6b7280"
  mist: "#9ca3af"
  chalk: "#e5e7eb"
  fine-line: "#e9e9e9"
  pewter: "#bbbbbb"
  ash: "#f0f0f0"
  forest: "#16a34a"
  ember: "#dc2626"
typography:
  body:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.08em"
  small:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: "monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  heading:
    fontFamily: "system-ui, -apple-system, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
    letterSpacing: "-0.01em"
rounded:
  track: "2px"
  micro: "5px"
  sm: "6px"
  md: "7px"
  lg: "8px"
  xl: "16px"
  pill: "24px"
  circle: "50%"
spacing:
  xs: "6px"
  sm: "8px"
  md: "16px"
  lg: "20px"
  xl: "32px"
  chat-padding: "40px"
components:
  upload-button:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.iris}"
    rounded: "{rounded.lg}"
    padding: "9px 14px"
  upload-button-hover:
    backgroundColor: "{colors.iris}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.lg}"
    padding: "9px 14px"
  send-button:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.circle}"
    size: "40px"
  send-button-hover:
    backgroundColor: "{colors.iris}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.circle}"
    size: "40px"
  source-chip:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.slate}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  source-chip-hover:
    backgroundColor: "{colors.iris-soft}"
    textColor: "{colors.iris}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  chat-input:
    backgroundColor: "{colors.fog}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "11px 18px"
  mode-toggle-active:
    backgroundColor: "{colors.iris}"
    textColor: "{colors.canvas}"
    padding: "4px 12px"
  mode-toggle-default:
    backgroundColor: "{colors.fog}"
    textColor: "{colors.iron}"
    padding: "4px 12px"
---

# Design System: Not ChatGPT

## 1. Overview

**Creative North Star: "The Quiet Lab"**

This is a workspace for doing work, not for performing it. Every surface holds back until there is something to show. The sidebar sits silently until there are documents; the chat panel holds a single grounding prompt; the dev panel fills with data only after a query runs. The violet is the only note of personality — used exactly where the interface speaks (buttons, active states, focus rings) and nowhere else.

The system rejects three things explicitly. First, the purple soup: generic SaaS violet splashed on every card, gradient, and hover state — the iris here is rare and therefore meaningful. Second, the dark hacker aesthetic: neon on black, monospace everything, trying to signal technical seriousness by cosplaying a terminal. Third, the tutorial-clone flatness: default white with no spacing rhythm, no considered typography, no hover states. This project is a portfolio artifact. It should be immediately readable as crafted.

The tone is the same as the name: dry, confident, and uninterested in impressing you. The execution is what impresses.

**Key Characteristics:**
- Light, not dim — main canvas is white, surfaces step up to fog (#fafafa), never to gray
- Violet touches exactly where action lives — no ambient violet, no decorative violet
- Tonal depth without shadows — surfaces are differentiated by background color, not elevation
- System font rendered with care — weight, size, and letter-spacing carry all hierarchy
- Dev panel telemetry as a feature, not an afterthought — latency bars, chunk inspector, session stats are first-class

## 2. Colors: The Iris Palette

One accent, used surgically. Every other surface is a graduated neutral.

### Primary
- **Iris** (`#7c3aed`): The single interactive accent. Upload button border and fill-on-hover, active mode toggle, chat input focus ring, send button hover state, source chip hover, typing indicator dots via {colors.iris-mid}, kb item hover background via {colors.iris-hover}. Its rarity is what gives it weight.
- **Deep Indigo** (`#3b1fa8`): User message bubble text. Darker sibling to Iris — grounds the user's voice without introducing a second accent hue.

### Neutral
- **Canvas** (`#ffffff`): Main chat area background, source chips, dev panel stat cards. The starting layer.
- **Fog** (`#fafafa`): Sidebar, dev panel, chat input at rest. One step above canvas — creates structural depth without a visible border.
- **Ash** (`#f0f0f0`): Assistant message bubble. Neutral container that doesn't compete with the answer text.
- **Iris Tint** (`#f3f0ff`): User message bubble background. Connects user input to the primary hue without raising contrast.
- **Iris Faint** (`#ede9fe`): Progress bar background track. The lightest possible violet signal.
- **Iris Soft** (`#f5f3ff`): Source chip hover background. Confirms the hover without harshness.
- **Iris Hover** (`#f0ecff`): Sidebar item hover. Same role — confirms position, does not shout.
- **Iris Mid** (`#c4b5fd`): Typing indicator dots. Animated at reduced opacity — passive state, active movement.
- **Ink** (`#111111`): Primary text, send button default. Near-black rather than absolute — reduces harshness on a white canvas.
- **Slate** (`#374151`): Secondary text, latency millisecond values, chunk file names. One step down from Ink.
- **Iron** (`#6b7280`): Mode toggle inactive labels. Recessive, readable, clearly secondary.
- **Mist** (`#9ca3af`): Placeholders, empty-state text, sidebar icons, kb delete icon at rest. Signals absence without hiding it.
- **Chalk** (`#e5e7eb`): Primary border and divider. Sidebar edge, input bar top, dev panel outer edge, source chip border.
- **Fine Line** (`#e9e9e9`): Dev panel internal section dividers and stat card borders. Slightly tighter than Chalk for higher-density contexts.
- **Pewter** (`#bbbbbb`): Dev panel section labels (CHUNKS, STATS, LATENCY). Recessive label styling for a dense information context.

### Status
- **Forest** (`#16a34a`): Upload success confirmation text. Positive signal only — never decorative.
- **Ember** (`#dc2626`): Upload errors, API errors, chat errors, kb item delete hover. Danger signal only.

**The One Voice Rule.** Iris (`#7c3aed`) appears on ≤15% of any given screen. It is used on interactive elements and their states, and nothing else. If a surface feels like it needs more violet, the answer is to remove chrome from the surface, not to add violet.

**The No-Gradient Rule.** No color gradients anywhere. Background-clip-text with a gradient is prohibited. Tonal steps in this system come from distinct flat values, not blends.

## 3. Typography

**Body / UI Font:** system-ui, -apple-system, sans-serif  
**Mono Font:** monospace (dev panel only)

**Character:** System font treated with precision. Every weight, size, and spacing choice is deliberate — this is not "default browser rendering." The heading is tight (`letter-spacing: -0.01em`). Labels are full-caps with wide tracking. The body is comfortable and readable at 14px with 1.6 line height. The dev panel switches to monospace — not for aesthetics, but because it renders numerical data and code excerpts.

### Hierarchy
- **Heading** (700 weight, 1.05rem, letter-spacing -0.01em): Sidebar title only. One instance per page.
- **Body** (400 weight, 14px, 1.6 line-height): Chat messages, document names, button labels, general UI text. Cap line length at 65-75ch in prose contexts.
- **Small** (400 weight, 12-13px): Source chips, status feedback (upload ok/error), disclaimer text, chat error text.
- **Label** (700 weight, 10px, uppercase, letter-spacing 0.07-0.09em): Section headers in the sidebar ("KNOWLEDGE BASE") and dev panel ("CHUNKS", "STATS", "LATENCY"). All-caps marks structural hierarchy without a size increase.
- **Mono Body** (400 weight, 12px, monospace): Dev panel text — chunk content, file names, stat values read as code-adjacent data. Switches register intentionally.

**The System Font Rule.** No Google Fonts, no font loading. The system font stack renders at native quality, loads at zero cost, and matches the OS context the engineer is already working in. This is not a compromise — it is a choice.

## 4. Elevation

This system is flat by default. Surfaces are differentiated by background color (Canvas → Fog), not by shadow.

The single exception is the chat input focus ring: `box-shadow: 0 0 0 3px rgba(124,58,237,0.08)`. This is a state indicator, not structural elevation — it signals keyboard focus on the field without implying the field is lifted.

### Named Rules
**The Flat-By-Default Rule.** Surfaces sit at rest without shadows. Depth is read from color step (Canvas → Fog → Ash), from borders (Chalk), and from contrast — not from blur and spread. If you reach for `box-shadow` on a surface, reach harder for a tonal background instead.

## 5. Components

### Buttons

**Two buttons with opposite philosophies.**

- **Upload Document (ghost-to-fill):** Outlined with Iris border and Iris text at rest; fills to Iris background with white text on hover. `border-radius: 8px`. Full-width in the sidebar. Transition: 150ms `background`, `color`.
- **Send (icon circle):** 40×40px solid Ink circle, arrow icon in white. Hovering shifts fill to Iris. `border-radius: 50%`. Scales to 0.93 on active press. Disabled state: 35% opacity. Transition: 150ms `background`, 100ms `transform`.

Both buttons make the same color promise: Ink is the resting authority; Iris is the active signal.

### Mode Toggle

Segmented control housing three options (Hybrid / Semantic / Keyword). Container: 1px Chalk border, `border-radius: 7px`, `overflow: hidden`. Individual segments: 11px text, no border-radius, `border-right: 1px solid {colors.chalk}`. Active segment: Iris fill, white text, 600 weight. Inactive: Fog background, Iron text. Hover on inactive: Iris-soft background, Iris text. Last segment has no right border.

This is a toggle, not tabs — all three options are always visible and reachable in one click.

### Chat Input

Pill-shaped text field: `border-radius: 24px`, Fog background at rest, 1.5px Chalk border. Focus: border shifts to Iris, background shifts to Canvas, focus ring `0 0 0 3px rgba(124,58,237,0.08)`. Placeholder in Mist. Expands to full available width minus the send button.

### Chat Bubbles

- **User:** Iris Tint background (`#f3f0ff`), Deep Indigo text. `border-radius: 16px` with `border-bottom-right-radius: 4px` — the asymmetric corner marks origin without a label.
- **Assistant:** Ash background (`#f0f0f0`), Ink text. `border-radius: 16px` with `border-bottom-left-radius: 4px` — mirror of user convention.

Max-width 68% of the chat panel width. No avatars, no timestamps.

### Source Chips

Inline citation badges below each assistant message. White background, Chalk border, Slate text, 12px, `border-radius: 6px`, `padding: 4px 10px`. On hover: Iris border, Iris text, Iris-soft background. Includes a small arrow icon when linked to a blob URL. Transition: 120ms `border-color`, `color`, `background`.

### Sidebar Document Items

List items with no explicit border. Hover: Iris-hover (`#f0ecff`) background fill, `border-radius: 7px`, 120ms transition. Delete button hidden at rest, revealed on item hover — Mist icon, red fill (`#fee2e2`) background with Ember icon on delete hover. 120ms all transitions.

### Dev Panel (Signature Component)

A 300px fixed-width right panel in monospace. Divided into sections by Fine Line borders. Three areas:

1. **Stats grid:** 2-column grid of small stat cards (white bg, Fine Line border, `border-radius: 6px`). Stat value in 14px/700/Ink; stat key in 10px/uppercase/Pewter.
2. **Latency bars:** Each row has a 40px Pewter label, a flex track (Ash background, Slate fill, `height: 4px`, `border-radius: 2px`), and a right-aligned ms value in Slate/600. Bars animate width on update (300ms transition).
3. **Chunk inspector:** Accordion items — collapsed show file name + score badge; expanded show raw chunk text in a scrollable 150px area, Fog background, Fine Line top border.

The dev panel is not a debug tool. It is a feature. Engineers reviewing this portfolio see their retrieval pipeline exposed in real time. Recruiters see evidence of depth.

### Typing Indicator

Three Iris-mid (`#c4b5fd`) dots, 7px diameter, `border-radius: 50%`. Vertical bounce animation — `translateY(-6px)` at 40% — staggered by 200ms. Duration 1.2s, infinite. Sits inside an assistant bubble wrapper to maintain layout consistency.

## 6. Do's and Don'ts

### Do:
- **Do** use Iris (`#7c3aed`) only on interactive elements and their states — buttons, focus rings, active toggles, hover confirmations.
- **Do** use tonal background stepping (Canvas → Fog) to create structural depth before reaching for a border.
- **Do** write label text in 10px/700/uppercase with `letter-spacing: 0.07em` — the size step and tracking carry the hierarchy without a visible divider.
- **Do** use asymmetric border-radius on chat bubbles (`border-bottom-right-radius: 4px` for user, left for assistant) — this is the only visual convention that marks message origin.
- **Do** show empty states that breathe — a centered Mist paragraph, nothing more. No illustrations, no CTAs.
- **Do** keep the dev panel visible at all times. Its presence signals intentionality. Hiding it signals shame about the implementation.
- **Do** respect `prefers-reduced-motion` for the typing indicator bounce and any future transitions.

### Don't:
- **Don't** use `background-clip: text` with a gradient. Gradient text is decorative noise and prohibited without exception.
- **Don't** spread Iris (`#7c3aed`) across backgrounds, dividers, headings, or decorative elements. If a surface is violet, it has failed.
- **Don't** use dark backgrounds on any surface — not the sidebar, not the chat, not the dev panel. This tool is not a terminal emulator.
- **Don't** introduce a second accent color. The palette is Iris + neutrals. A second accent hue dilutes the signal.
- **Don't** add border-left or border-right stripes (greater than 1px) as color accents on list items or cards. The kb item hover uses a full background tint — not a stripe.
- **Don't** add any box-shadow to resting surfaces. The Flat-By-Default Rule is not a guideline; it is a constraint.
- **Don't** use `#000000` or `#ffffff` literally. Ink (`#111111`) is the darkest value; Canvas (`#ffffff`) is white — but tint it to `#fafafa` (Fog) when the context is a panel or sidebar.
- **Don't** make the interface look like a generic SaaS product — rounded cards in a grid, gradient CTAs, purple-on-purple backgrounds. If someone could guess the color scheme from the category name alone, start over.
- **Don't** make it look like a hacker terminal — neon, dark background, everything monospace. The dev panel uses mono for a reason; nothing else should borrow that register.
- **Don't** add loading states that are purely decorative. The typing indicator is meaningful (it shows the request is live). A spinner on an already-fast operation is noise.
