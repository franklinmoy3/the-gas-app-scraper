# This Dockerfile bundles the scraper into a deployable container
FROM python:3-bookworm
WORKDIR /usr/local/app

# Install Selenium dependencies
RUN apt-get update
RUN apt-get install -y firefox-esr wget bzip2 libxtst6 libgtk-3-0 libx11-xcb-dev libdbus-glib-1-2 libxt6 libpci-dev
RUN curl -L https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz | tar zx
RUN mv geckodriver /usr/local/bin/

# Copy project files
COPY src Pipfile Pipfile.lock ./

# Create and use non-root user
RUN useradd app
USER app

# Install pipenv and project dependencies
RUN python3 -m pip install pipenv
RUN python3 -m pipenv install

# Run the scraper
CMD ["python3", "src/scraper.py", "--structured-logging", "--log-level=INFO"]