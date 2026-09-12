from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app import models  # noqa: E402,F401

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {"db": db, **{name: getattr(models, name) for name in models.__all__}}


if __name__ == "__main__":
    app.run(debug=True)
