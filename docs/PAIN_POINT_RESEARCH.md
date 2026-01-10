# Pain Point Discovery Research

This document captures research and planning for features that help identify community pain points from scraped Facebook group data.

## Goal

Use forage to scrape Facebook groups, then feed data to an LLM to extract:
- Common problems people have
- Unmet needs in the community
- App/software ideas that solve real problems

---

## Research Findings

### Pain Point Linguistic Patterns

Sources: [PainOnSocial](https://painonsocial.com/blog/pain-point-analysis-guide-2), [Reddit Hunters](https://www.reddithunters.com/blog/how-to-do-market-research-on-reddit), [Mural UX Guide](https://www.mural.co/blog/identify-user-pain-points)

| Pattern Type | Keywords/Phrases |
|--------------|------------------|
| **Seeking** | "looking for", "does anyone know", "recommendations for", "where can I find", "anyone have experience with" |
| **Wishing** | "wish there was", "would be nice if", "someone should build", "why isn't there", "if only" |
| **Frustration** | "frustrated with", "tired of", "hate when", "annoying that", "sick of", "can't stand" |
| **Alternatives** | "alternative to [X]", "something like [X] but", "better than [X]", "instead of [X]" |
| **Questions** | Posts ending in "?", starting with "how do I", "has anyone", "what's the best", "where can I" |
| **Needs** | "I need", "we need", "looking to hire", "trying to find" |

### Engagement as Problem Signal

Sources: [Problem Sifter](https://www.problemsifter.com/blog/reddit-market-research), [tldv.io](https://tldv.io/blog/how-to-identify-user-pain-points/)

- **High comment counts** often indicate unresolved problems - people pile on because no good solution exists
- **Recurring posts** about the same topic = persistent pain point
- **Upvotes/reactions** validate that many people share the pain
- Posts that appear in "top" across multiple timeframes are significant
- 3-star reviews (on review platforms) contain the most balanced, detailed feedback

### Problem Validation Criteria

Sources: [Founders Network](https://foundersnetwork.com/guide-to-startup-idea-validation/), [PitchDrive](https://www.pitchdrive.com/academy/problem-solution-fit-for-startups-how-to-achieve-success), [Startup Grind](https://www.startupgrind.com/blog/the-startup-framework-to-validate-your-idea-before-you-spend-1/)

#### Tier 1 Problem Test
> "Customers will be so focused on solving their first 3 problems that they won't have time for your product — EVEN if you have the best product."

Ask: Is this in someone's top 3 problems? If not, they won't pay.

#### Painkiller vs Vitamin
- **Painkiller**: Must-have, solves urgent pain (people will pay)
- **Vitamin**: Nice-to-have, improves life (people use but won't pay)

#### Validated Problem Characteristics
A validated problem means the customer has:
1. Confirmed there is a problem or pain point
2. Believes the problem can and should be solved
3. Actively invested effort, time, or money trying to solve it
4. Doesn't have circumstances preventing them from fixing it

#### Key Statistic
> "A staggering 42% of startups fail because there's no market need for their product."

### LLM-Optimized Output

Sources: [Pinecone Chunking Guide](https://www.pinecone.io/learn/chunking-strategies/), [Redis LLM Chunking](https://redis.io/blog/llm-chunking/)

- **~500 words per chunk** is optimal (about 650 tokens)
- Include **metadata** (engagement, date) for context
- **Semantic grouping** of similar content helps
- **10-15% overlap** between chunks preserves context
- Strip unnecessary fields to reduce token usage

---

## Proposed Features

### Phase 1: LLM-Ready Output Format (v1.1.0 - PATCH)

Add `-f llm` output format optimized for API consumption.

**Goals:**
- Reduce token usage by stripping unnecessary fields
- Add computed signals (is_question, pain_point_matches)
- Flatten structure for easier processing
- Include engagement metrics prominently

**Proposed Output Structure:**
```json
{
  "metadata": {
    "group_name": "Wilmington NC Community",
    "group_url": "https://facebook.com/groups/...",
    "scraped_at": "2025-01-10T15:00:00Z",
    "date_range": {"since": "2025-01-03", "until": "2025-01-10"},
    "post_count": 47,
    "total_comments": 342,
    "total_reactions": 891
  },
  "posts": [
    {
      "content": "Does anyone know a good plumber? Our bathroom has been leaking for weeks and we can't find anyone reliable.",
      "engagement": {
        "reactions": 42,
        "comments": 31
      },
      "signals": {
        "is_question": true,
        "pain_keywords": ["looking for", "can't find"],
        "pain_score": 2
      },
      "timestamp": "2025-01-10T14:30:00Z",
      "id": "post_abc123"
    }
  ]
}
```

**Implementation Notes:**
- Strip: author profile_url, individual reaction breakdowns (unless non-zero), empty comment arrays
- Add: `signals` object with computed indicators
- Keep: content, engagement summary, timestamp, id

**CLI Usage:**
```bash
forage scrape GROUP -f llm -o posts.json
forage scrape GROUP -f llm --days 7 | claude-api-script.py
```

---

### Phase 2: Pain Point Filter (v1.2.0 - MINOR)

Add `--pain-points` flag to filter posts containing pain point language.

**Goals:**
- Dramatically reduce noise (500 posts → 50 relevant ones)
- Configurable keyword list
- Score posts by number of pattern matches

**Default Keyword Categories:**
```yaml
seeking:
  - "looking for"
  - "does anyone know"
  - "recommendations for"
  - "where can I find"
  - "anyone have experience"

wishing:
  - "wish there was"
  - "would be nice"
  - "someone should build"
  - "why isn't there"

frustration:
  - "frustrated with"
  - "tired of"
  - "hate when"
  - "annoying that"
  - "sick of"

alternatives:
  - "alternative to"
  - "something like"
  - "better than"
  - "instead of"

needs:
  - "i need"
  - "we need"
  - "trying to find"
  - "help me find"
```

**CLI Usage:**
```bash
# Use default keywords
forage scrape GROUP --pain-points

# Custom keywords file
forage scrape GROUP --pain-points --keywords pain_keywords.yaml

# Minimum pain score
forage scrape GROUP --pain-points --min-pain-score 2
```

**Configuration File (optional):**
```yaml
# ~/.config/forage/pain_keywords.yaml
seeking:
  - "looking for"
  - "need help finding"
  # ... custom additions
```

---

### Phase 3: Engagement Sorting (v1.2.0 - MINOR)

Add `--sort` flag to order posts by engagement.

**Proposed Weighting:**
```
engagement_score = reactions + (comments * 2)
```

Rationale: Comments indicate active discussion/unresolved problem. Reactions are passive agreement.

**CLI Usage:**
```bash
forage scrape GROUP --sort engagement --limit 50
forage scrape GROUP --sort comments
forage scrape GROUP --sort reactions
forage scrape GROUP --sort recent  # default, by timestamp
```

---

### Phase 4: Question Detection (v1.2.0 - MINOR)

Add `--questions-only` flag to filter to question posts.

**Detection Logic:**
- Ends with `?`
- Starts with question words: who, what, where, when, why, how, does, has, can, is, are, should, would, could
- Contains phrases like "does anyone", "has anyone", "can someone"

**CLI Usage:**
```bash
forage scrape GROUP --questions-only
```

---

### Phase 5: Summary Statistics (v1.2.0 - MINOR)

Add `--stats` flag for quick overview.

**Output:**
```
Group: Wilmington NC Community
Posts scraped: 156
Date range: 2025-01-03 to 2025-01-10

Engagement:
  Total reactions: 2,341
  Total comments: 1,892
  Avg reactions/post: 15.0
  Avg comments/post: 12.1

Content Analysis:
  Questions: 43 (28%)
  Pain point language: 67 (43%)

Top Pain Keywords:
  "looking for": 23 posts
  "does anyone know": 18 posts
  "frustrated": 11 posts
  "recommendations": 9 posts
```

---

### Future: Recurring Theme Detection (v2.0.0?)

Group similar posts to identify patterns. Complex - requires embeddings.

**Possible Approaches:**
1. Simple TF-IDF clustering (no external API)
2. Call embedding API (OpenAI, Claude) for semantic similarity
3. Keyword co-occurrence analysis

**Output:**
```
Theme: Plumbing Issues (12 posts)
  - "Looking for reliable plumber..."
  - "Does anyone know a good plumber..."
  - "Frustrated with plumber who..."

Theme: Restaurant Recommendations (8 posts)
  - "Best Mexican food in town?"
  - "Looking for good sushi..."
```

---

## Open Questions

### Answered
- **Keyword customization?** → Yes, will support custom keyword files
- **Engagement weighting?** → Default to `reactions + (comments * 2)`, can adjust later
- **Output format?** → JSON primary, potentially JSONL for streaming

### Still Open

1. **Comments in LLM output?**
   - Include top N comments per post?
   - Or just comment count?
   - Comments often contain solutions/recommendations

2. **Time-based analysis?**
   - Track same problem appearing over weeks/months?
   - Would require storing historical data

3. **Multi-group analysis?**
   - Compare pain points across different community groups?
   - Identify problems unique to one area vs universal?

4. **Integration with analysis tools?**
   - Direct pipe to Claude API?
   - Export for other tools (Obsidian, Notion)?

5. **Prompt templates?**
   - Ship suggested prompts for analyzing the output?
   - Example: "Analyze these posts and identify the top 5 problems people are trying to solve..."

---

## Implementation Roadmap

| Version | Features | Type |
|---------|----------|------|
| v1.0.3 | LLM-ready output format (`-f llm`) | PATCH |
| v1.1.0 | Pain point filter, engagement sorting, question detection, stats | MINOR |
| v2.0.0 | Recurring theme detection (if needed) | MAJOR |

---

## Resources

### Research Sources
- [PainOnSocial - Pain Point Analysis Guide](https://painonsocial.com/blog/pain-point-analysis-guide-2)
- [Reddit Hunters - Market Research on Reddit](https://www.reddithunters.com/blog/how-to-do-market-research-on-reddit)
- [Mural - Identify User Pain Points](https://www.mural.co/blog/identify-user-pain-points)
- [Founders Network - Startup Idea Validation](https://foundersnetwork.com/guide-to-startup-idea-validation/)
- [Pinecone - Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/)

### Similar Tools (for reference)
- [PainOnSocial](https://painonsocial.com/) - Reddit pain point finder
- [BigIdeasDB](https://bigideasdb.com/) - Reddit keyword generator
- [GummySearch](https://gummysearch.com/) - Reddit audience research

---

## Notes

- 42% of startups fail due to no market need - validation is critical
- Focus on "painkiller" problems, not "vitamin" improvements
- Recurring mentions across time = validated pain point
- High comments often = unresolved problem worth solving
