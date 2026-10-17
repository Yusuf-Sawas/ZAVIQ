# ZAVIQ

ZAVIQ is a phone-first smart development workspace. The long-term vision is project and file management, architecture planning, sourced technical research, error diagnosis, patch review, and export preparation.

This repository is at an early stage. It currently contains one small workflow:

**Dune planning workflow powered by an LLM**

```
prompt -> input validation -> model request -> JSON -> Pydantic validation -> saved JSON file
```

It is not a multi-agent system and it is not autonomous. The model is asked once for a structured plan, the result is validated, and the result is saved. Nothing the model suggests is executed or created on disk.

## Scope of this stage

Written in this repository:
- Python package `zaviq`: data schemas, a model client, the Dune workflow, and a command-line entry point.
- Offline tests in `tests/test_dune.py`. They use a fake model client and need no network or API key.
- A GitHub Actions workflow: offline tests on every push and pull request, plus a manual live run.

Not built yet:
- Verification of the offline tests on GitHub Actions (the first green run).
- A live run with a valid API key and model name.
- Fixer and Scout agents.
- Any user interface.
- A permanent API or server.
- Database, hosting, or deployment.

## Offline tests vs. live model call

- **Offline tests** use a fake model client. They make no network calls and need no API key. The test data is fake and exists only inside the tests. Passing tests show that validation and error handling work. They do not show that a real model produces good plans.
- **Live run** is a manual GitHub Actions run that calls the real Gemini API with your key. Only this proves the model integration works. Access to the Gemini API depends on your account, region, and model. It is not assumed.

## One-time setup on GitHub (works from a phone)

If you do not see the repository Settings tab, open the repository in your browser with "Desktop site" enabled.

1. Repository → Settings → Secrets and variables → Actions.
2. Tab **Secrets** → New repository secret. Name: `GEMINI_API_KEY`. Paste your key into GitHub's form only. Never put it in code, README, issues, chats, or workflow inputs.
3. Tab **Variables** → New repository variable. Name: `GEMINI_MODEL`. Value: a model name your own account can use (check it in Google AI Studio). Do not guess a name.

## Run the tests from your phone

1. Commit or push any change to the repository.
2. Open the **Actions** tab, then the latest **ZAVIQ checks** run.
3. The job **Offline tests** should be green. It uses no secrets.

## Run the live model test manually

1. Actions tab → **ZAVIQ checks** → **Run workflow**.
2. Choose branch `main`, type a general, non-sensitive project idea in `prompt`, and run.
3. When the job **Live Dune run** succeeds, open the run page and download the artifact `dune-plan`. It is a zip file containing `outputs/dune-plan.json`.
4. If the run fails, no artifact is uploaded and the job log shows a short error message.

## Security notes

- Workflow inputs, logs, and artifacts are not a place for secrets. In a public repository, treat them as public.
- The API key lives only in GitHub Secrets and is read from the environment variable `GEMINI_API_KEY`. The model name is read from `GEMINI_MODEL`.
- The live run never starts automatically (not on push, not on pull request) and never writes to the repository.

## Command line

```
python -m zaviq.cli --prompt-file INPUT_PATH --output OUTPUT_PATH
```

Exit codes: `0` success, `1` planning failed, `2` invalid input, `3` missing configuration, `4` output could not be written.

## Limitations

- No interface, no permanent API, no Fixer, no Scout.
- GitHub Actions is not a server. It is used only for tests and short manual runs.
- Plan quality depends on the model and the prompt. The output is validated for structure, not for correctness.

## Status

- Offline tests on GitHub Actions: not yet verified.
- Live model integration: not yet verified.

Update this section only after you have seen a green test run or a real artifact.

## No promises

This project makes no claim about prizes, program acceptance, or grants.
