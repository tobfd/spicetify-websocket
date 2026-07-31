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
