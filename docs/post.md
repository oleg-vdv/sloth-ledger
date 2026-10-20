---
title: 114,000 Kazakhs got a letter from the tax office. A local Gemma answers most of it for you.
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Since January, banks in Kazakhstan report a personal card to the tax office when it receives transfers from **100 or more different people in each of three months in a row**, adding up to **more than 12 minimum wages** (1,020,000 ₸, about $2,000). People call it the 100/3/12 rule. After the first quarter, about 114,000 people got a notice in their taxpayer account.

Most of them are not tax dodgers. They bake cakes to order, tutor kids, split rent with flatmates, or have a big family that sends money around. But the notice asks one question — where did this money come from? — and answering it means going through hundreds of transfers and sorting them into "customer", "my mum", "my flatmate paying her half of the rent".

**sloth-ledger** does that sorting. You give it your card statement and two or three sentences in your own words:

> I bake cakes to order at home, customers pay by card transfer. Mum is Гульнара С., she helps every month. I rent the flat with Динара К. and Асель М.; they send me their share and I pay the landlady.

and it gives you back:

- the 100/3/12 check, month by month;
- every sender sorted into customer / family / shared expenses / loan / unclear, each with a one-line reason;
- **a short list of the people the model wasn't sure about** — the only ones you have to look at;
- a draft reply to the notice, where every number and every name comes from the statement.

The lazy part is the point: you don't open 400 transfers. You read a list of {{FLAGGED}} names, fix the ones that are wrong, and copy the letter.

## Demo

{{VIDEO}}

The demo uses a synthetic statement: a home baker, July–September 2026, 537 operations, 205 people who sent her money. No real statement was used anywhere in this project.

## Code

{% github oleg-vdv/sloth-ledger %}

## How I Built It

The interesting decision was **what not to give the model**.

| Step | Who does it |
|---|---|
| Read the PDF statement | regex over the extracted text |
| Count senders per month, check 100/3/12 | plain Python |
| Group 400+ transfers into 205 people | plain Python |
| Decide who each person is | **Gemma 4, running locally in Ollama** |
| Say "I'm not sure" | Gemma, plus guard rails |
| Write the letter | a template filled by code |

Arithmetic on money is exactly where a small model is most likely to be confidently wrong, and a wrong total in a letter to the tax office is the worst possible bug. So the model never sees the ledger and never computes the rule. It gets one compact profile per sender — number of transfers, months active, median and range of amounts, days of the month — plus the owner's notes, and answers with a category, a confidence and a reason, constrained by a JSON schema.

Then the code distrusts the answer:

- a sender the model invents is dropped;
- a sender it skips becomes "unclear";
- malformed JSON or an unknown category becomes "unclear";
- "unclear" or low confidence goes to the human list.

Every failure lands on the human, never in the letter.

The model runs on an RTX 5050 laptop in my flat (8 GB of VRAM), served by Ollama, reached over the home network. Two things I learned the slow way:

- **Gemma 4 is a thinking model.** With thinking left on, my first batch of twelve senders took ten minutes and returned nothing. `"think": false` brought it to under a minute.
- **12B didn't fit.** `gemma4:12b` needs 8.9 GB with an 8K context, so 3 GB spilled to the CPU and the GPU sat at 22% load. The smaller `{{SMALL_MODEL}}` fits entirely in VRAM.

{{BENCH_TABLE}}

The overall accuracy is flattering — 200 of the 205 senders are customers, so a model that calls everyone a customer gets 97.6%. The numbers I actually care about are the five people named in the notes, and how many senders get sent back to the human.

## Why Does Open Innovation Matter?

A card statement is the most personal document most people own: full names, amounts, the rhythm of their week. Uploading it to a hosted API in order to answer a letter from the tax office would be a small privacy incident of its own — and in Kazakhstan, personal data law makes the person who uploaded it responsible for where it went.

With an open-weight model the whole thing runs on hardware you can point at. Nothing in sloth-ledger calls the internet; the statement goes from your disk to your GPU and back. That isn't a feature I added on top. Without an open model there is no version of this tool I'd be comfortable telling my neighbour to use.

## The Lazy Payoff

{{PAYOFF}}

## Prize Categories

Best Use of Gemma — Gemma 4 ({{SMALL_MODEL}} and 12B) runs locally in Ollama as the classifier.
