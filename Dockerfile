# This Dockerfile bundles the scraper into a deployable container
FROM python:3-bookworm
WORKDIR /usr/local/app

# Install Selenium dependencies
RUN apt-get update
RUN apt-get install -y firefox-esr=115.14.0esr-1~deb12u1 wget bzip2 libxtst6 libgtk-3-0 libx11-xcb-dev libdbus-glib-1-2 libxt6 libpci-dev
RUN curl -L https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz | tar zx
RUN mv geckodriver /usr/local/bin/

# Copy project files
COPY costco-gas-station-urls-us.json Pipfile Pipfile.lock ./
COPY src ./src

# Create and use non-root user
RUN useradd --create-home app
USER app

# Set Git config (maybe use a service account later?)
RUN git config --global user.name Franklin Moy
RUN git config --global user.email franklinmoy3@gmail.com

# Add GitHub to known SSH hosts
RUN mkdir -p -m 700 /home/app/.ssh && ssh-keyscan -H github.com >> /home/app/.ssh/known_hosts

# Install pipenv and project dependencies
RUN python3 -m pip install pipenv
RUN python3 -m pipenv install --system

# Run the scraper
CMD ["python3", "src/scraper.py", "--no-write-to-file", "--structured-logging", "--use-mounted-deploy-key", "--log-level=INFO"]
