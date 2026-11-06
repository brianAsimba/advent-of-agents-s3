-- Which agent is hungriest? The local version of the course's query over Cloud Trace spans.
SELECT
  agent,
  variant,
  COUNT(DISTINCT session)                                  AS sessions,
  COUNT(*)                                                 AS llm_calls,
  ROUND(1.0 * COUNT(*) / COUNT(DISTINCT session), 1)       AS calls_per_session,
  SUM(input + cache_write + cache_read)                    AS input_tokens,
  SUM(output)                                              AS output_tokens,
  ROUND(100.0 * SUM(cache_read) / MAX(SUM(input + cache_write + cache_read), 1), 1) AS cache_hit_pct,
  ROUND(SUM(usd), 4)                                       AS usd
FROM calls
WHERE ts >= :since
GROUP BY agent, variant
ORDER BY usd DESC;
