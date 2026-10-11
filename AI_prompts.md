# AI Prompts — Homework 5: Campus Customs Multi-Agent Operations

A copy of every prompt typed while vibe coding this homework, one section per problem.

---

## Setup (before Problem 1)

> Ok today we are going to be working on Homework number 5 for AI so put everything I work on today in the Homework 5 folder under AI CC. The background is that campus customs multi-agent operations is an agentic team that runs the cc shop. open tickets land on a board, custom orders, rent, unpaid bills, discount requests, and what the shop has to do. there will be three pieces that need to interact -- mcp server, a fastapi backend with a multi agent team and a react dashboard so a human can observe and approve requests.
>
> the agen should have full connectivity - so any agent may delegate tasks. In this homework, we will build the Boss, Inventory, Accounting, Facilities, and Customer Service agents.
>
> The data is attached. Unzip it so that you have data/campus_custom.db. the tools will update the database as tickets get resolved. make a copy of the database file called data/campus_customs_new.db and point your mcp server and backend at that working copy but keep the original untouched so i can reset when i want to restart resolving tickets. I've also attached the rules of the shop in a pic.
>
> There are 11 problems and I will tell you each of them and the name of the problem. are you ready for the first one?

*(Attachments: `data (1).zip`; screenshot of "Rules of this shop".)*

---

## Problem 1: Vibe coder prompts

> Great, Problem 1: Vibe coder prompts: make AI_prompts.md and update it as I work with a copy of everything I type here as I vibe code. Make sure there is one section per problem that includes the title and number and the prompts. This is the end of the first problem

---

## Problem 2: Study the Campus Customs database

> Problem 2: Study the Campus Customs database: open data/campus_customs.db and look at each table and its fields. copy the original file to data/campus_customs_new.db which we will later update this copy. study the three open tickets so they you understand how they link to the tables.
>
> Start output/harness.md. for each of the tables, list the fields and one short line on why that table is important for the agents. this harness file we will keep growing later.

---

## Problem 3: Build the MCP server

> Now Problem 3: Build the MCP server: write an MCP server in mcp_server/ using FastMCP. it should talk to data/campus_customs_new.db. you don't need to connect or run it in this problem. every agent in this homework assignment uses the tools in the MCP server. you can add more tools to it later but for now write three tools you know that will need tickets in the data. keep the names clear and never invent data - only use info that is given in the database.

> Still problem 3 -- in output/harness/md list each of the three MCP tools. for each tool include: the table it reads, which ticket it helps unlock (101,102,or 103), and one sentence on why the tool is correct for that ticket. don't make it so vague like "reads inventory" -- be sure to tie the tool to the ticket.
>
> also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses and the three tools it has.

---

## Problem 4: Add the MCP Server to vibe coder and test each tool

> Now problem 4: Add the MCP Server to vibe coder and test each tool.
>
> Add the MCP server to this project so that you can call the tools. save the connection JSON text in .mcp.json at the root of the project (or however you save local MCP server lists).
>
> then, once connected, test each of the three MCP tools. save the evidence in output/mcp_smoke.json.
>
> For each tool include: the prompt asked/typed, the tool name, and the tool output which should match the values in data/campus_customs_new.db

---

## Problem 5: Build the agent team and grow the MCP tools

> Now Problem 5: Build the agent team and grow the MCP tools
>
> build the agentic team for campus customs using pydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. INclude the prompts, models, agent loops so they can delegate the work to each other with full connection.
>
> put the agent prompts in backend/prompts/ -- one file per agent. put data types in backend/models.py, and the agent files under backend/ (the layout can vary as long as the 5 rols are super clear). use the portkey_api_key and ONLY gpt-6-luna for every agent.  no other model.
>
> I'll write each prompt in my own words with the shop rules that agent needs. its important that the prompts are detailed and cover all aspects of an agents work and scope so that it scores well. let me know if mine do not do that.
>
> Add any tools the agents need to the MCP server so they can work to open tickets. shop facts come from the MCP server over data/campus_customs_new.db and do not invent a second shot tools layer that bypasses MCP
>
> wire agents so they append to output/audit_trail.json as they run -- for each agent loop step, record enough so that it can be audited later. append to this file and do not wipe after each run.
>
> in output/harness.md list every agent and each MCP tools including the ones added in this problem along with the table the tool uses. add a short safety section -- the guardrails a real busines would want to use when agents interact with real customers and money plus limits that keep token use in check.
>
> update mcp_server/README.md so the tool list matches what we have now

> Ok for the missing prompts, here they are:
>
> boss: this agent will read every ticket, decide who will work on it and make all the final calls
>
> inventory: checks the stock by SKU and size and spots any shortcomings and figures out which vendor can restock
>
> accounting: watches cash and invoices and checks margins. it is also responsible for preparing payments or purchase orders that are required for humans to then approve
>
> facilities: this one handles the shop space so anything to do with leases, rent, etc
>
> customer service: this one should create messages that will be sent to customers
>
> need anything else?

---

## Problem 6: Plan the three tickets

> Ok now Problem 6: Plan the three tickets
>
> Before wiring the backend, write what you expect the team to do on each open ticket. build output/desk_tickets.html which is a page that can be double clicked with one tab per ticket (101, 102, and 103). add empty Cash and Reflection tabs for later problems and leave them blank or with a short "coming later" note just for now.
>
> on each ticket tab, fill in an Expected section only (leave room for an Actual section you'll fill after running the agents).

> Still Problem 6, for each ticket's expected section, write who the boss should call first and why, all the agent delegations you expect - not "boss calls everyone", and which MCP tools you expect the run to use.
>
> plans that send every specialist on every ticket will score poorly. so you will compare this plan to what actually happens when the agents resolve the 3 tickets. make sense?

---

## Problem 7: Backend routes

> Problem 7: Backend routes
>
> your react frontend dashboard (next problem) needs a backend to call. in backend/main.py, use FastAPI and add routes that:
>
> return the 3 tickets and whether each is open or resolved,
> take a ticket id and run the agent team on it
> return recent agent events -- what each agent said and which tools were used so the board can refresh
> approve a payment or purchase after a human clicks approve (agents only prepare the pay and this route is actually what changes cash)
> return the current checking balance from cash_accounts
> reset the database to original values when you want to try a new run
>
> then from the backend/ folder, start the server with this to turn on the backend at http://localhost:8000  so the frontend dashboard can call these routes:
> uvicorn main:app --reload --port 8000
>
> in output/harness.md list each rout in one line (what url and what it does)
>
> Thanks!

---

## Problem 8: Agent dashboard

> Ok now Problem 8: Agent dashboard
>
> build the front end dashboard in frontend/ with react + vite + typescript. the page should call the routes built in problem 7 and at minimum the board must include:
> -list all 3 tickets
> -let you pick one ticket and start the agent team on it
>
> * show each agent and what they are saying and doing while the ticket runs
> * mark a ticket resolved when the run is done
> * show a short summary for each ticket on what each agent did
> * let a human approve a pay or purchase when prompted
> * finally, show the checking balance which it should drop after an approved pay
>
> make the dashboard look really really good - feel free to be creative with the layout and feel. people actually look at these so its important its very nice looking
>
> Now tell the frontend to talk to the backend at http://localhost:8000 and on the backend, allow the vite page origin which is usually http://localhost:5173 so the browser is allowed to call those routes. you can start the board with this: npm run dev
>
> which opens the react desk in browser so you can pick and watch the agents
>
> write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how tickets that are resolved and cash show up) and why -- be sure to include the creative choices that make it feel special and unique.

---

## Problem 9: Resolve the tickets

> Ok now problem 9: Resolve the tickets
>
> before testing the agents on a full run over the 3 tickets, reset the working database data/campus_customs_new.db again so it starts clean. note the starting checking balance and then run all 3 tickets on the board (101,102, and 103) until each has been resolved
>
> open output/desk_tickets.html from problem 6 and on each ticket tab fill in the actual section from this run -- which agents worked, what they delegated to others, which tools were used. keep your expected section so you can compare each of them to each other.
>
> on the cash tab of the same output/desk_tickets.html, itemize the money with starting checking balance (after the reset), for each ticket -- how cash changed when the ticket was resolved and why so which pay or purchase and dollar amount, and ending checking balance -- which must match cash_accounts in the working database
>
> wrong cash math loses points even if the board accurately shows each resolved ticket so make sure its all correct!!!
>
> save:
> output/resolved_tickets.json for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
>
> output/resolved_board.html as a page you can double click with a screenshot of the React board for each resolved ticket so 101, 102 and 103
>
> then append real runs to output/audit_trail.json. finish output/harness.md so it covers tables, mcp tools, five agents, api routes, dashboard, and safety rules. make sense?

---

## Problem 10: Reflection

> Ok now Problem 10: Reflection
>
> open output/desk_tickets.html and fill out the Reflection tab. please answer in my own vice and be detailed and thorough. My vibe is super smart, business-minded student, knowledgable in AI and retail businesses
>
> How would you evaluate the performance of the agents on each ticket and why?
> For each ticket, how did Actual compare to the Expected plan you wrote earlier?
> What would have been simpler as one agent with tools and why?
> Describe three new problems Campus Customs might face that this agent team could solve with the tools you built
> Describe three new problems Campus Customs might face that this agent team could not solve with the tools you build, and explain the tools and agents you would need to solve them.
>
> Make sure to tie each answer to this app and the three tickets that were run -- use the ticket tabs and Cash tab on the same page as evidence. Generic AI essays without Campus Customs details will score poorly so don't do that!!

> approve #1 and #2 as Elise

---

## Problem 11: Submit to GitHub

> Ok finally Problem 11: Submit to GitHub
>
> push the code to a public github repository so my class graders can clone it. I'll then submit the repo URL to canvas but also put it in output/github_url.text
>
> do not push reach .env to github repo. be sure to include both database files under data/ (the original and the working copy) so graders can easily see and run my app
>
> the files should look something like this (attached) and README should explain: copy to original DB to the working copy when need a clean run, start MCP server, start FastAPI backend, start the React board and reset the DB before a full 3 ticket run.
>
> any questions for any of these problems now that it's finished?

*(Attachment: screenshot of the expected `hw5/` file tree.)*

> expand the agent prompts and push the update
