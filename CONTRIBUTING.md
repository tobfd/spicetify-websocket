I am always happy to receive contributions to **spicetify-websocket**! Here is how you can get started:

---

## 🚀 How to Contribute

1. **Fork** this repository on GitHub.
2. **Install** development dependencies and set up **pre-commit** hooks:
   ```bash
   pip install -e .
   pip install -r requirements-dev.txt
   pre-commit install
   ```
3. **Make your changes** in a new branch (e.g., `feature/my-feature` or `fix/my-fix`) and format your commit messages according to the [Conventional Commits](https://www.conventionalcommits.org/) specification.
4. **Create a Pull Request** against the `master` branch.

---

## 🧪 Testing & Docs

### Running Tests
Before submitting your changes, run the test suite locally with `pytest`:

```bash
pytest
```

### End-to-End Tests with the Extension

`tests/e2e` runs the real [spicetify-connect-api](https://github.com/tobfd/spicetify-connect-api) extension in Node.js (with a fake Spotify API) against the real server and validates every message against the extension's `protocol/messages.schema.json`. They need Node.js 22+ and a checkout of the extension:

```bash
git clone https://github.com/tobfd/spicetify-connect-api ../spicetify-connect-api
SPICETIFY_EXTENSION_DIR=../spicetify-connect-api pytest tests/e2e
```

Without `SPICETIFY_EXTENSION_DIR` they are skipped. Tests for newer protocol features are skipped automatically when the extension is older. CI runs them against the extension's `master` branch on every pull request and weekly; to test against another branch, run the workflow manually with `extension_ref` or set the repository variable `SPICETIFY_EXTENSION_REF`.

---

### Building Documentation
You can build the Sphinx documentation locally to check if your changes render correctly:

```bash
cd docs
make html  # On Windows: .\make html
```

After the build succeeds, open `docs/_build/html/index.html` in your browser to inspect the result.

---

## 💡 Other Resources

* Feel free to open a [Bug Report or Feature Request](https://github.com/tobfd/spicetify-websocket/issues) on GitHub.
* Please ensure all interactions follow our [Code of Conduct](https://github.com/tobfd/spicetify-websocket?tab=coc-ov-file).
