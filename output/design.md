# Dashboard design: Campus Customs Ops Desk

**Stack:** React + Vite + TypeScript in `frontend/`. Run `npm run dev` to serve it at http://localhost:5173. It talks to FastAPI at http://localhost:8000 (`VITE_API_URL` in `frontend/.env`). The backend's CORS settings allow `localhost:5173`.

## The idea: a night-shift control room
The page should feel like a real operations desk watched at 2 a.m. The background is ink black with a soft pink aurora and a faint dot grid. Each agent has its own colored light. The course's black-and-pink style is the base, but pink is saved for things that need a human (the Run button, payment cheques, the "Resolved" stamp). Everything else stays calm, so your eye goes where action is needed.

## Layout (three columns, left to right = the order of work)
1. **The board (left):** the three tickets as **claim-check stubs**. Each has perforated notches cut out of both sides, a big serif `№ 101` and a dashed tear line. A progress bar at the top shows how many are resolved (e.g. 0/3 to 3/3).
2. **The work (center):**
   - **Ticket hero:** the selected ticket's subject, requester, its database facts (SKU, size, qty, invoice, lease) as monospace chips, and one big **Run the team** button.
   - **The floor:** the five agents arranged in a pentagon with Boss at the top. Faint dotted lines connect every pair to show full connectivity, meaning anyone can hand off to anyone. Each hand-off in the current run lights up as a line that fades from the sender's color to the receiver's. While the receiver is working, animated dashes flow along it, so you can watch work move between agents.
   - **Live wire / Debrief tabs:** the live conversation while a run is going. When it finishes, the view flips automatically to a per-agent debrief.
3. **The money (right, sticky):** the **Checking** vault and the **Needs your signature** approval queue. They're always visible, because cash is what a human has to protect.

## How the agents read differently
Each agent has a **color, a monogram and a "voice"**, so you can tell them apart without reading names:

| Agent | Color | Voice in the wire |
|---|---|---|
| Boss | pink | **Serif memo type** (Fraunces). The manager's lines read like a memo. |
| Inventory | mint | Clean sans |
| Accounting | gold | **Tabular numbers**, so figures line up like a ledger |
| Facilities | lavender | Clean sans |
| Customer Service | sky blue | **Italic**, like a quoted, friendly reply |

- Every message has a colored left edge in the agent's color.
- Tool calls appear as monospace chips like `check_stock(sku="CC-TEE-WHITE", size="S")`. `delegate_task` chips are highlighted in pink.
- Tool results are folded under a "↳ 2 tool results" line, so the wire stays readable but nothing is hidden.
- Hand-offs get their own banner: `BOSS ⟶ INVENTORY` plus the task, with a dashed border that blends the two agents' colors. Refused hand-offs show in red with the reason.

On the floor, each agent station has a status:
- *Off the clock*: dimmed.
- *Thinking*: a dashed orbit ring spins around the avatar and it glows.
- *Using a tool*: the tool name appears in the agent's color.
- *Reported back*: a check badge.

A speech bubble under each agent shows its latest line.

## Resolved tickets
- The stub's phase chip moves from **Open** to **Team working** (pink pulse) to **Needs your approval** (amber pulse) to **Resolved** (green).
- When a ticket resolves, a pink **RESOLVED rubber stamp** lands on its stub with a little overshoot, and the subject fades. The board's progress bar fills from pink to green.
- A ticket is marked resolved when its run finishes and nothing is waiting on a human, or when the human pays its last pending approval.
- The **Debrief** tab shows:
  - the hand-off route as pills (e.g. `Boss → Inventory`, `Inventory → Accounting`);
  - model calls, tool calls and tokens used;
  - one card per agent with its outcome badge, its summary in its own words, the actions it took and the tools it used.

## Cash
- **Big serif balance** (`$3,400.00`, with cents set smaller). When a payment goes through, the number **rolls down** like an odometer instead of jumping, and the vault flashes pink once, so the drop is impossible to miss.
- **Runway bar** under it: mint shows the money that's free, and animated pink hazard stripes show what's waiting on you. The legend gives the free amount and the pending total in dollars. If approving everything would overdraw the account, an amber warning appears.
- **Payments look like cheques:** lined paper, "Pay to" in italic serif, a big pink amount, a memo line (`Invoice #501` or `Rent · lease #1`), who prepared it, and what checking would be left with. There's a **Signing as** field (remembered in the browser), and *Approve & pay* is disabled until a name is entered. That makes it physically clear a human signs, not an agent. If the cheque is larger than the balance, it warns that the pay tool will refuse it.
- A toast confirms each payment with the before and after, e.g. `Checking $3,400.00 → $2,560.00`.

## Small touches
- The desk-calendar chip shows **the shop's "today"** (`desk.date_today`, Aug 31 2026), not the real date, which mirrors the shop rule.
- The status pill reads "Team on shift" and shows the model (`gpt-6-luna`).
- Reset needs a second click to confirm. It's disabled while a run is going.
- Fonts are bundled locally (Fraunces, Inter, JetBrains Mono), so there are no CDN calls.
- Keyboard focus rings are visible, live regions announce new wire lines and balance changes, and everything respects `prefers-reduced-motion`. The layout stacks to two columns, then one, on smaller screens.

## Why
- **Watchability:** people look at this board, so motion is used only to show real state changes: hand-off dashes, the orbit ring while thinking, the balance rolling down, the stamp landing.
- **Trust:** cash and approvals never scroll away. Payments look like cheques a person signs, which reinforces "agents prepare, humans pay."
- **Scannability:** color plus monogram plus voice lets you follow a five-agent conversation at a glance, and the debrief turns the long wire into one card per agent.
