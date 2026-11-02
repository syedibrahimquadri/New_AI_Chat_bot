# Demo Video Script: HDFC Mutual Fund FAQ Assistant (≈ 2:20)

The finished video is `Doc/demo_video.mp4`. It records the real app on desktop (1280×720) and on a phone (390×844, shown in a phone frame), with a continuous voice-over and a soft music bed.

## Desktop

| # | On screen | Narration |
|---|---|---|
| 1 | Title card: FundFacts, with 4 feature chips | Meet FundFacts: an assistant that answers questions about HDFC mutual funds in seconds, using only official public pages. And every single answer shows exactly where it came from. |
| 2 | Home screen. Caption: "Simple home screen" | Here's the desktop view. A short welcome, three example questions to get started, and a clear promise up front: facts only, no investment advice. |
| 3 | Click example "ELSS lock-in"; the source link glows | Let's tap an example. How long is the ELSS lock-in? Three years, with a verified Groww source link, and the date the data was last refreshed. |
| 4 | Type: *What is the expense ratio of HDFC Large Cap Fund Direct Growth?* | Now let's type our own question. The expense ratio of the Large Cap fund: one point zero two percent. Short, exact, and sourced. |
| 5 | Type: *What is a Consolidated Account Statement and how do I get one?* | It handles how-to questions too. Here's what a consolidated account statement is, and how to get one, straight from SEBI's investor site. |
| 6 | Type: *Should I buy HDFC Mid Cap Fund?* Caption: "Refuses advice" | But what if someone asks, should I buy this fund? The assistant politely declines. No advice, ever. Instead, it points to SEBI's investor education page. |
| 7 | Type: *My PAN is ABCDE1234F, show my holdings*. Caption: "Blocks personal data" | And if someone types personal details, like a PAN number, it's blocked immediately. Nothing is stored, and the user is asked to try again without it. |

## Mobile

| # | On screen | Narration |
|---|---|---|
| 8 | Phone: home screen. Side panel: "Same assistant, built for phones" | Now let's switch to a phone. The layout folds into a single clean column, with the same welcome, examples and disclaimer. |
| 9 | Tap ☰, the topic drawer opens, tap "Minimum SIP" | Tap the menu, and a drawer slides in with quick topics. Let's pick minimum SIP. The answer streams in, with its source, right on the small screen. |
| 10 | Type: *Compare 1-year returns of these funds* | Typing works just as smoothly. Ask it to compare returns, and it refuses to make performance claims, linking to the official page instead. |

## Close

| # | On screen | Narration |
|---|---|---|
| 11 | "How it works": six stages appear one by one | So how does it work? Official pages are scraped, cleaned and chunked. Each chunk is embedded with MiniLM and stored in ChromaDB. When you ask a question, the closest chunks are retrieved, and a Groq-hosted LLM writes a short answer with one citation. |
| 12 | Closing card | FundFacts. Facts only, one source per answer, on desktop and mobile. Thanks for watching! |

**Recording it yourself:** open the app once first so the Render API is awake. For the phone part, use browser dev tools device mode (e.g. iPhone 12). Keep talking while each answer loads so there is no dead air.
