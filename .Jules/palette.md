## 2024-07-05 - Placeholder Context for API Key Fields
**Learning:** Placeholders like "sk-..." are visually informative but confusing for screen-reader users when directly mapped to aria-labels (e.g. `aria-label="sk-..."`). Sighted users use the placeholder combined with surrounding context, but screen readers read the aria-label out of context.
**Action:** When adding `aria-label` to form inputs based on placeholder text, ensure the label text explicitly describes the field's purpose (e.g., "API Key") rather than copying purely stylistic or demonstrative placeholders.
