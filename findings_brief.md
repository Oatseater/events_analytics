# Events Analytics: three findings

> **Simulated data. Concept demo, not real company data.** All names and figures are invented to demonstrate the analysis.

Scope: 8 finished medical conferences, Feb 2025 to Sep 2026, plus tickets sold so far for the ones still to come. 4,889 tickets. AED 6,894,660 in ticket revenue. 75.0% of ticket holders came to the finished events. 2 upcoming events are left out of turnout until they happen.

### 1. WhatsApp sign-ups show up. Cold Call sign-ups often don't.

Number: 82.7% of people who registered through WhatsApp came. 62.5% of Cold Call ones did. That's a gap of 20.2 percentage points. Cold Call also turns the fewest leads into tickets: 38.0%, against 68.7% for WhatsApp.

Why it matters: a paid ticket with nobody behind it is still an empty seat on the day. [PLACEHOLDER: if sponsor deals are judged on turnout, say so here.]

What to do: move some Cold Call time to WhatsApp. Try a WhatsApp reminder for people who signed up through Cold Call.

*Dashboard: Marketing Funnel, "Turnout by channel".*

### 2. Late buyers are the likeliest to pay and not come

Number: 34.8% of Late tickets were no-shows, 520 people. Early Bird: 14.6%. That's about 2.4 times as often. People who booked in the last 14 days missed 35.3% of the time. People who booked more than 90 days out missed 15.2%.

Why it matters: the money is already in, so no-shows look free. They still mean fewer people in the hall.

What to do: sell earlier. Make Early Bird easier to find and run it longer. Send Late buyers a confirmation in the final week.

*Dashboard: Overview, "No-shows by ticket type".*

### 3. Nursing Symposium Abu Dhabi 2026 didn't break even

Number: it needed 317 paid tickets at its average price (AED 854) to cover AED 270,000 of fixed cost. It sold 295. That's 22 short, and a loss of AED 18,000. 228 of those ticket holders came. It filled 39.3% of its 750 seats. Sponsorship isn't in this data, so this is tickets only.

Why it matters: eight weeks out it had sold 159 tickets, 50.2% of what it needed. The problem was visible early.

What to do: check every event against its break-even line eight weeks out, with a fallback agreed in advance, like a smaller venue. The Overview now does this for upcoming events, as a range.

*Dashboard: Overview, the bright bar in "Ticket revenue by event" and "Upcoming events".*

---
*Written by `make_brief.py` from the SQL in `queries/`. No number here is typed by hand. Simulated data. Concept demo, not real company data. All names and figures are invented to demonstrate the analysis.*
