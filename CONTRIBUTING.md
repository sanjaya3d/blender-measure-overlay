# Contributing

Thanks for your interest in improving Measure Overlay!

## Reporting bugs

Please [open an issue](../../issues/new/choose) and include:

- Your Blender version and operating system
- What you expected and what happened
- Any error text from **Window > Toggle System Console** (Windows) or the terminal you launched Blender from

## Suggesting features

Open an issue describing the problem you're trying to solve. Small, focused ideas are the easiest to add.

## Pull requests

1. Fork the repo and create a branch.
2. Keep changes focused: one fix or feature per pull request.
3. Run the tests before pushing:
   ```bash
   python -m unittest discover -s tests -v
   ```
4. If you change measuring or report logic, add or update a test in `tests/test_report.py`.
5. If you change drawing code, test it in a real Blender session and mention which version(s) you tried.
6. Add a line to `CHANGELOG.md` under an `Unreleased` heading.

## Code style

- Plain Python 3.10+, no external dependencies.
- Keep the measuring logic (`build_report` and friends) separate from drawing code so it stays testable without Blender.

## Questions

Not sure if something is a bug or an idea? Message SANJAYA3D on [Facebook](https://www.facebook.com/sanjaya3d).

## License

By contributing, you agree that your contributions are licensed under GPL-3.0-or-later, the same as the project.
