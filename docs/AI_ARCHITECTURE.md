# AI architecture

AI tasks are isolated behind `LLMProvider`: document extraction, requirement analysis, acceptance-criteria generation, change classification, bug-vs-change classification, verification planning, observation analysis, result judging and delivery summarization.

Every response is structured and validated before persistence. Each `LLMRun` records provider, model, prompt version, latency, token usage, estimated cost and status.

Browser content is untrusted input. System policy, test objective and observed content remain separate. Destructive actions are disabled by default.
