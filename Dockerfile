FROM python:3.5

RUN apt-get update && apt-get install -y --no-install-recommends libgeos-dev \
      && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /srv/app /srv/iso

WORKDIR /srv/app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN pip install -e .

#Add app user
RUN useradd --system --home-dir=/srv/app app \
      && chown -R app:app /srv/app /srv/iso

VOLUME /srv/iso

ENTRYPOINT ["sensorml2iso", "--output_dir", "/srv/iso"]
