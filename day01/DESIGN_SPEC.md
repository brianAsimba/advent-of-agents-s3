# adlc-day1
Owner: Brian Asimba
Model: Claude (claude-opus-5-5 via ADK + LiteLLM, Anthropic API)
May: answer weather and time questions with get_weather and get_current_time
May not: call any other tool, store user data, or act on external systems
Success: picks the right tool for each question (see tests/ and the trace from `adk run`)
