# Campfire Vision

> Refer to this doc when making product or architecture decisions. If a change works against it, call that out.

## Campfire is a taste engine and a catalog of taste

We don't catalog restaurant *facts* (hours, ratings, menus, addresses). Those come live from Places and other sources, and we throw them away after use. We catalog what nobody else has: how restaurants relate to people's taste.

### What we store

1. **Restaurant IDs only, for facts.** Use the provider's ID (e.g. Google place ID) as a stable key to attach our own data to. Fetch the facts live at query time.
2. **User taste profiles.** Rich, weighted attributes ("loves counter seating, natural wine, regional Chinese; dislikes scenes"), not just cuisine counts. This is the core proprietary asset.
3. **Restaurant taste profiles and match data.** For each restaurant: who it matches ("people with taste X loved this") plus a niche profile of what makes it distinctive. This is how we surface interesting, under-the-radar places instead of the same popular ones.

### Principles

- **Never limit discovery to restaurants we've stored.** Any restaurant from any source can be a candidate.
- **Optimize for interesting, not popular.** Popularity is a weak signal at best and a penalty at worst.
- **Stay independent of any one data source.** Places, editorial and web sources are inputs, not the product.
- **Agents are first-class clients.** The UI and MCP tools sit on the same core.
