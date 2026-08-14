"""handspan CLI: discover | replay | operator | validate | catalog | invoke."""

# ruff: noqa: B008

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from handspan.llm.client import load_dotenv
from handspan.replay.loader import load

load_dotenv()

app = typer.Typer(no_args_is_help=True, add_completion=False)
ARTDIR = Path("evidence/artifacts")


@app.command()
def discover(
    goal: str = typer.Option(...),
    target: str = typer.Option(...),
    cassette: Path | None = typer.Option(None),
    live: bool = typer.Option(False),
    headed: bool = typer.Option(False),
    evidence_dir: Path | None = typer.Option(None),
) -> None:
    from handspan.discovery.agent import discover as run

    dest = run(
        goal,
        target,
        cassette_path=cassette,
        live=live,
        headless=not headed,
        evidence_dir=evidence_dir,
    )
    print(f"artifact: {dest}")


@app.command()
def replay(
    artifact: Path = typer.Option(...),
    overlay: Path | None = typer.Option(None),
    input: list[str] = typer.Option([], "--input"),  # noqa: A002
    attended: bool = typer.Option(False),
    persist_outputs: bool = typer.Option(False),
    headed: bool = typer.Option(False),
) -> None:
    from handspan.replay.executor import replay as run

    params = dict(part.split("=", 1) for part in input)
    result = run(
        artifact,
        params,
        overlay=overlay,
        mode="attended" if attended else "unattended",
        persist_outputs=persist_outputs,
        headless=not headed,
    )
    print(result.model_dump())
    raise typer.Exit(0)


@app.command()
def operator(port: int = 8090) -> None:
    import uvicorn

    from handspan.operator.app import app as op

    uvicorn.run(op, host="127.0.0.1", port=port)


@app.command()
def validate(artifact: Path = typer.Argument(...)) -> None:
    load(artifact)
    print("ok")


@app.command()
def catalog(json_out: bool = typer.Option(False, "--json")) -> None:
    tools = _catalog()
    if json_out:
        print(json.dumps(tools, indent=2))
    else:
        for t in tools:
            print(f"{t['name']}: {t['description']}")


@app.command()
def invoke(
    capability: str = typer.Argument(...),
    member_id: str | None = typer.Option(None),
    extra: list[str] = typer.Option([], "--input"),
) -> None:
    from handspan.replay.executor import replay as run

    path = _find(capability)
    params = dict(part.split("=", 1) for part in extra)
    if member_id:
        params["member_id"] = member_id
    result = run(path, params, persist_outputs=True)
    print(result.model_dump())


def _find(cap_id: str) -> Path:
    for p in sorted(ARTDIR.glob("*.yaml")):
        art = load(p)
        if art.capability.id == cap_id or p.stem.startswith(cap_id):
            return p
    raise typer.BadParameter(f"no artifact {cap_id}")


def _catalog() -> list[dict]:
    tools = []
    for p in sorted(ARTDIR.glob("*.yaml")):
        if p.parent.name == "overlays":
            continue
        art = load(p)
        if art.capability.status != "approved":
            continue
        tools.append(
            {
                "name": art.capability.id,
                "description": art.capability.description or art.capability.name,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        i.name: {"type": "string", "description": i.description or ""}
                        for i in art.inputs
                        if i.sensitivity != "secret"
                    },
                    "required": [
                        i.name for i in art.inputs if i.required and i.sensitivity != "secret"
                    ],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {o.name: {"type": o.type} for o in art.outputs},
                },
                "outcomes": [o.code for o in art.outcomes],
            }
        )
    return tools


def main() -> None:
    app()


if __name__ == "__main__":
    main()
