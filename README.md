<div align="center">
  <img align="center" src="https://imgur.com/eoe8Xsv.jpg" height="200px" alt="Image of Buttercup, from 1998's Powerpuff Girls">
</div>
<h1 align="center">buttercup</h1>

<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

Discord keeper extraordinaire!

Responsible for display name enforcement and whatever else comes her way, Buttercup is a python bot running on Discord.py. 

### Running Buttercup

In order to run buttercup, [poetry](https://python-poetry.org/) is used to manage and install dependencies.

Apart from this, a `.toml` configuration file is expected. Below is a default `config.toml`:
```
[Discord]
token = "<YOUR DISCORD BOT SECRET HERE>"

[Reddit]
client_id = "<YOUR REDDIT CLIENT ID HERE>"
client_secret = "<YOUR REDDIT CLIENT SECRET HERE>"
user_agent = "grafeas.org.buttercup:v0.1.0 (contact u/<YOUR USERNAME HERE>)"

[guild]
name = "Test Bubbles"

[Admin]
role = "ToR Mods"

[NameValidator]
accepted_role = "Visitor (0)"
restrict_role = "New User"
restrict_channel = "new-user"
welcome_channel = "off-topic"

[Blossom]
email = ""
password = ""
api_key = ""
```
The `secrets` section contains all secrets required to run Buttercup:
- `discord` is Discord's bot secret

The `guild` section currently contains only the Discord server's name, to make sure the bot connects to the correct server.
The other sections are related to the identically named cogs. The documentation of these options can be found within the source code.

`main.py` can then be ran to initialize Buttercup.

### Development

[*coming soon*]

### Adding new functionality

[*coming soon*]

## Pre-commits

Buttercup uses `pre-commit` to help us keep everything clean. After you check out the repo and run `poetry install`, run `pre-commit install` to configure the system. The first time that you run `git commit`, it will create a small venv specifically for checking commits based on our toolset. All of these are installed as part of the regular project so that you can run them as you go -- don't get taken by surprise when you go to commit! The toolchain as written invokes the following tools:

- seed-isort-config
  - This sets .isort.cfg with all of the third-party modules that are in use.
- isort
  - Searches Python files for imports that are in the wrong order, then offers you the option of fixing them.
- black
  - Opinionated code formatter; automatically fixes issues.
- flake8
  - formatting checker and linter; does not automatically fix issues.
