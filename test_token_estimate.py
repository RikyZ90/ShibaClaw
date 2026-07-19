from shibaclaw.helpers.helpers import estimate_prompt_tokens
runtime_block = "This is a test runtime block."
tokens1 = estimate_prompt_tokens(runtime_block)
tokens2 = estimate_prompt_tokens([{"role": "system", "content": runtime_block}])
print(f"String input tokens: {tokens1}")
print(f"List of dicts input tokens: {tokens2}")
