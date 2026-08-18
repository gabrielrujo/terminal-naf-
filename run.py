"""Ponto de entrada do Terminal NAF V2."""

import os

from terminal_naf import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("NAF_HOST", "0.0.0.0"),
        port=int(os.environ.get("NAF_PORT", "5000")),
        debug=os.environ.get("NAF_DEBUG", "0") == "1",
    )
