from openlit_config import init

# OpenLIT's init() must be called before importing travel_agent to properly instrument the application
init()

from travel_agent import app  # noqa: E402

if __name__ == "__main__":
    app.run()
