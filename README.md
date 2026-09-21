# JobFit

A job application tracker with AI fit-scoring.

## The problem

Applying to jobs at volume is mostly reading, not applying. A candidate opens twenty postings a
week and mentally checks each against their own CV — years, stack, seniority, location. Most
postings fail on one line buried in the middle, so the reading is almost entirely wasted.

The second half is memory: after thirty applications across LinkedIn, career pages, and email
referrals, you no longer know which are live, which went silent, and which you never followed up on.

**Who has it:** final-year students and early-career developers running an active job search,
applying to 10–30 roles a month, with no recruiter and no ATS of their own.

## The 10x claim

> Deciding whether a posting is worth applying to took 15 minutes of careful reading.
> It now takes 20 seconds of reading a score and three bullet points.

## The non-goal

**No auto-apply, no form-filling.** JobFit does not submit applications on your behalf and does not
drive a browser into third-party ATS systems. It advises and tracks; the human applies.

## A note on email

The weekly digest is delivered over SMTP to **Mailpit**, a local mail catcher that runs as a
container in this stack (web inbox on `:8025`). This replaces a hosted test-mail account: there is
no signup, no credentials to leak, and anyone who clones this repo can watch a digest arrive
without registering for anything. `EMAIL_PROVIDER=smtp` in `.env` points the same code at a real
provider, and `EMAIL_PROVIDER=file` writes messages to disk instead of sending.

This is a provider choice, not a concept swap - concept 5 (reporting: PDF + email) is implemented
in full either way.

## Status

Under construction. Setup commands, the concept → file-location table, the demo path, and the
architecture diagram land in this file as the build progresses.

## Future ideas

Parked deliberately, not built:

- Browser extension for one-click ingest from a job board
- Slack bot for digest delivery
- Salary analytics across tracked postings
- Cover-letter drafting
