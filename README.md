![Image of Buttercup, from 1998's Powerpuff Girls](https://i.imgur.com/wx8BXyT.png)

<h1 align="center">buttercup</h1>

<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

Discord keeper extraordinaire!

Responsible for display name enforcement and whatever else comes her way, Buttercup is a python bot running on Discord.py. 

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
