# Contributing

1. Create a Python virtual environment

2. Install the identity package in editable mode:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the tests:

    ```bash
    python -m pytest
    ```

4. Make the docs:

    ```bash
    pip install -r docs/requirements.txt
    python -m mkdocs build
    cd docs
    make html
    ```
