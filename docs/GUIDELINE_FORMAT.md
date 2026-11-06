# Writing guidelines the platform can read

Upload a markdown file in **Brand Vault > Import guidelines** (or `POST /api/vault/guidelines/import`). Each rule is one line:

```
## Tone
- [T-1] No slang. avoid: "awesome", "gonna" use: "great", "going to" severity: low ref: Brand Guidelines v3, section 1.1
```

- A `## Heading` sets the category: **Tone, Terminology, Messaging, Accessibility, Visual, Claims**.
- `- [CODE] Title.` starts a rule. The code is your own (letters, optional dash, number).
- `avoid: "a", "b"` and `use: "x", "y"` turn the rule into an automatic check. If both lists have the same length they are paired one to one. Otherwise every avoided word gets all the alternatives.
- `severity: low | medium | high`. If you leave it out, a new rule is `medium` and an existing rule keeps its severity.
- `lock: yes` means a person must always decide (reviewers cannot be skipped).
- `ref: ...` is the text shown to writers as the source of the rule.
- Lines without `avoid:` become **documentation rules** (listed in the Vault, shown in insights, not checked automatically).
- If the code already exists, the importer updates its title, severity and lock, and only replaces the automatic check when the new line has `avoid:`.

## Built-in checks you can tune in the Vault

| Code | Checks | Tunable in the UI |
|---|---|---|
| TERM-1 | glossary: approved and banned terms | glossary tab |
| T-1 | slang | pairs via guideline import |
| T-2 / T-3 | exclamation marks, ALL CAPS | severity, lock, on/off |
| A-1 | sentence length (default 28 words) | severity, on/off |
| A-2 / A-3 / A-4 | alt text, link text, colour contrast 4.5:1 | severity, on/off |
| A-5 | inclusive language | pairs via guideline import |
| M-1 | prices and offers must say "Terms apply" | severity, on/off |
| M-2 | no legal or tax promises (locked) | severity, on/off |
| V-1 / V-2 / V-3 | brand colours, brand fonts, image rules | assets (palette, fonts, image_rules) |
| C-1 to C-5 | claims: no source, wrong number, expired source, no source for number, comparisons | severity, lock, on/off |

Thresholds such as the sentence-length limit live in the rule's `config` (change with `PUT /api/vault/rules/<code>` and a `config` object).

## Facts

Facts are managed in **Brand Vault > Approved facts**. Write the `statement` as the plain sentence that is true, put the number exactly as it should appear in `value` (for example `Rs. 499` or `10,000+`), and add `keywords` that writers might use (the search uses them). Always add a source document, a page or section, an owner and an expiry date.
