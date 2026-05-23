# User Profile

Persistent personal profile used to personalize interactions.
Store durable user facts and preferences here.
Project status and workspace context belong in memory/MEMORY.md.

## Onboarding Behavior

Fields marked as `_unknown` below should be discovered **gradually through natural conversation** — never upfront, never all at once.
- Ask at most **one question per session**, when it feels natural and genuine
- Be **warm, curious, and a bit playful** — like getting to know someone, not filling a form
- Prioritize learning **Name** and **Language** first, then the rest over time
- Once a field is discovered, **update this file** replacing the `_unknown` annotation with just the real value, no extra text

## Basic Information

- **Name**: _unknown — ask the user their name in a casual, curious way ("hey, I don't even know what to call you!")
- **Timezone**: _unknown — infer from context clues (e.g. "good morning", mentioned times) before asking directly
- **Language**: _unknown — infer from the language the user writes in, then confirm if unsure

## Preferences

### Communication Style

- [ ] Casual
- [ ] Professional
- [ ] Technical

_unknown — observe how the user writes and mirror it; update the checkbox above once clear_

### Response Length

- [ ] Brief and concise
- [ ] Detailed explanations
- [ ] Adaptive based on question

_unknown — infer from reactions to early responses; update the checkbox above once clear_

### Technical Level

- [ ] Beginner
- [ ] Intermediate
- [ ] Expert

_unknown — infer from vocabulary and questions; update the checkbox above once clear_

## Work Context

- **Primary Role**: _unknown — ask what they're working on to infer it ("what kind of stuff do you usually work on?")
- **Main Projects**: _unknown — let it emerge naturally from conversation topics
- **Tools You Use**: _unknown — pick up from mentions of IDEs, languages, commands used

## Topics of Interest

_unknown — note recurring themes from conversation and list them here once patterns emerge_

## Special Instructions

_unknown — ask only if the user seems to have strong preferences or mentions frustrations_

---

*Fields are filled in progressively as the assistant gets to know the user. Once a field is known, the `_unknown` annotation is removed and replaced with the actual value.*
